"""Background job runner.

Jobs are rows in the `job` table. A job function receives a JobContext to report progress.
Jobs run on a small thread pool (or inline when `settings.jobs_inline` is true, e.g. tests).
Registered job kinds can be retried from their stored params.
"""

import logging
import threading
from collections.abc import Callable
from concurrent.futures import ThreadPoolExecutor
from dataclasses import dataclass, field
from typing import Any

from sqlalchemy import Engine
from sqlmodel import Session

from app.core.config import Settings
from app.core.errors import NotFoundError, ValidationFailedError
from app.models import Job
from app.models.tables import utcnow

logger = logging.getLogger(__name__)


@dataclass
class JobContext:
    job_id: int
    engine: Engine
    settings: Settings
    params: dict[str, Any]
    counts: dict[str, Any] = field(default_factory=dict)
    _lock: threading.Lock = field(default_factory=threading.Lock)

    def progress(self, stage: str, progress: int, message: str = "", **counts: Any) -> None:
        with self._lock:
            self.counts.update(counts)
            with Session(self.engine) as session:
                job = session.get(Job, self.job_id)
                if job is None:
                    return
                job.stage = stage
                job.progress = max(0, min(100, progress))
                job.message = message
                job.counts = dict(self.counts)
                job.updated_at = utcnow()
                session.add(job)
                session.commit()


JobFn = Callable[[JobContext], None]
_REGISTRY: dict[str, JobFn] = {}


def register(kind: str) -> Callable[[JobFn], JobFn]:
    def decorator(fn: JobFn) -> JobFn:
        _REGISTRY[kind] = fn
        return fn

    return decorator


class JobRunner:
    def __init__(self, engine: Engine, settings: Settings) -> None:
        self.engine = engine
        self.settings = settings
        self._pool = ThreadPoolExecutor(max_workers=settings.job_workers, thread_name_prefix="job")

    def shutdown(self) -> None:
        self._pool.shutdown(wait=False, cancel_futures=True)

    def submit(self, kind: str, params: dict[str, Any], project_id: int | None = None) -> Job:
        if kind not in _REGISTRY:
            raise ValidationFailedError(f"Unknown job kind: {kind}")
        with Session(self.engine) as session:
            job = Job(kind=kind, params=params, project_id=project_id)
            session.add(job)
            session.commit()
            session.refresh(job)
        assert job.id is not None
        if self.settings.jobs_inline:
            self._run(job.id)
        else:
            self._pool.submit(self._run, job.id)
        with Session(self.engine) as session:
            refreshed = session.get(Job, job.id)
            assert refreshed is not None
            return refreshed

    def retry(self, job_id: int) -> Job:
        with Session(self.engine) as session:
            job = session.get(Job, job_id)
            if job is None:
                raise NotFoundError(f"Job {job_id} not found")
            if job.status not in ("failed", "succeeded"):
                raise ValidationFailedError("Only finished jobs can be retried")
            kind, params, project_id = job.kind, dict(job.params), job.project_id
        return self.submit(kind, params, project_id)

    def _set(self, job_id: int, **values: Any) -> None:
        with Session(self.engine) as session:
            job = session.get(Job, job_id)
            if job is None:
                return
            for key, value in values.items():
                setattr(job, key, value)
            job.updated_at = utcnow()
            session.add(job)
            session.commit()

    def _run(self, job_id: int) -> None:
        with Session(self.engine) as session:
            job = session.get(Job, job_id)
            if job is None:
                return
            kind, params = job.kind, dict(job.params)
        ctx = JobContext(job_id=job_id, engine=self.engine, settings=self.settings, params=params)
        self._set(job_id, status="running", progress=0)
        try:
            _REGISTRY[kind](ctx)
        except Exception as exc:
            logger.exception("Job %s (%s) failed", job_id, kind)
            message = getattr(exc, "message", None) or str(exc) or exc.__class__.__name__
            self._set(job_id, status="failed", error=message[:1000])
            return
        self._set(job_id, status="succeeded", progress=100, counts=ctx.counts)

import asyncio
import json
from collections.abc import AsyncIterator

from fastapi import APIRouter, Request
from fastapi.responses import StreamingResponse
from sqlmodel import Session

from app.core.deps import CurrentUser, SessionDep
from app.core.errors import NotFoundError
from app.jobs.runner import JobRunner
from app.models import Job
from app.schemas.api import JobOut, JobStarted

router = APIRouter(prefix="/jobs", tags=["jobs"])


def job_out(job: Job) -> JobOut:
    assert job.id is not None
    return JobOut(
        id=job.id,
        project_id=job.project_id,
        kind=job.kind,
        status=job.status,
        stage=job.stage,
        progress=job.progress,
        message=job.message,
        error=job.error,
        counts=job.counts or {},
        created_at=job.created_at,
        updated_at=job.updated_at,
    )


@router.get("/{job_id}", response_model=JobOut)
def get_job(job_id: int, _: CurrentUser, session: SessionDep) -> JobOut:
    job = session.get(Job, job_id)
    if job is None:
        raise NotFoundError(f"Job {job_id} not found")
    return job_out(job)


@router.post("/{job_id}/retry", response_model=JobStarted, status_code=202)
def retry_job(job_id: int, request: Request, _: CurrentUser) -> JobStarted:
    runner: JobRunner = request.app.state.jobs
    job = runner.retry(job_id)
    assert job.id is not None
    return JobStarted(job_id=job.id, project_id=job.project_id)


@router.get("/{job_id}/events")
async def job_events(job_id: int, request: Request, _: CurrentUser) -> StreamingResponse:
    """Server-sent events: `progress` while running, then `done` or `error`."""
    engine = request.app.state.engine

    async def stream() -> AsyncIterator[str]:
        last = ""
        while True:
            if await request.is_disconnected():
                return
            with Session(engine) as session:
                job = session.get(Job, job_id)
                if job is None:
                    yield f"event: error\ndata: {json.dumps({'message': 'Job not found'})}\n\n"
                    return
                payload = job_out(job).model_dump_json()
                status = job.status
            if payload != last:
                event = {"succeeded": "done", "failed": "error"}.get(status, "progress")
                yield f"event: {event}\ndata: {payload}\n\n"
                last = payload
            if status in ("succeeded", "failed"):
                return
            await asyncio.sleep(0.5)

    return StreamingResponse(stream(), media_type="text/event-stream")

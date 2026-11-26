"""FastAPI application factory."""

import importlib
import logging
from collections.abc import AsyncIterator
from contextlib import asynccontextmanager
from pathlib import Path

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import FileResponse
from fastapi.staticfiles import StaticFiles
from sqlmodel import Session, select

from app.api import auth, company, health, jobs, policies, projects, requirements
from app.core.config import Settings, get_settings
from app.core.db import get_engine, run_migrations
from app.core.errors import register_error_handlers
from app.core.logging import configure_logging
from app.core.security import hash_password
from app.jobs.runner import JobRunner
from app.models import User

logger = logging.getLogger(__name__)
# Importing these modules registers their background job kinds.
JOB_MODULES = (
    "app.pipeline.analyse",
    "app.pipeline.draft",
    "app.pipeline.extras",
    "app.pipeline.package",
    "app.services.company",
)
for _module in JOB_MODULES:
    importlib.import_module(_module)
FRONTEND_DIST = Path(__file__).resolve().parents[2] / "frontend" / "dist"


def seed_admin(settings: Settings, session: Session) -> None:
    if session.exec(select(User)).first() is not None:
        return
    session.add(
        User(
            email=settings.admin_email.strip().lower(),
            password_hash=hash_password(settings.admin_password.get_secret_value()),
            name=settings.admin_name,
        )
    )
    session.commit()
    logger.info("Seeded admin user")


def create_app(settings: Settings | None = None) -> FastAPI:
    settings = settings or get_settings()
    configure_logging(settings)
    engine = get_engine(settings)

    @asynccontextmanager
    async def lifespan(app: FastAPI) -> AsyncIterator[None]:
        for directory in (settings.data_dir, settings.files_dir):
            directory.mkdir(parents=True, exist_ok=True)
        run_migrations(settings)
        with Session(engine) as session:
            seed_admin(settings, session)
        app.state.jobs = JobRunner(engine, settings)
        logger.info(
            "BidReady API starting (env=%s, llm=%s, embeddings=%s)",
            settings.app_env,
            settings.effective_llm_provider,
            settings.embedding_provider,
        )
        yield
        app.state.jobs.shutdown()

    app = FastAPI(
        title="BidReady API",
        version="0.1.0",
        openapi_url="/api/openapi.json",
        docs_url="/api/docs",
        redoc_url=None,
        lifespan=lifespan,
    )
    app.state.settings = settings
    app.state.engine = engine
    register_error_handlers(app)

    if not settings.is_production and settings.cors_origin_list:
        app.add_middleware(
            CORSMiddleware,
            allow_origins=settings.cors_origin_list,
            allow_credentials=True,
            allow_methods=["*"],
            allow_headers=["*"],
        )

    for module in (health, auth, company, jobs, projects, requirements, policies):
        app.include_router(module.router, prefix="/api")

    if settings.is_production and FRONTEND_DIST.exists():
        app.mount("/assets", StaticFiles(directory=FRONTEND_DIST / "assets"), name="assets")

        @app.get("/{path:path}", include_in_schema=False)
        def spa(path: str) -> FileResponse:
            candidate = FRONTEND_DIST / path
            if path and candidate.is_file() and FRONTEND_DIST in candidate.resolve().parents:
                return FileResponse(candidate)
            return FileResponse(FRONTEND_DIST / "index.html")

    return app


app = create_app()

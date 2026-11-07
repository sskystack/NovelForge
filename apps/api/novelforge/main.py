from collections.abc import AsyncIterator
from contextlib import asynccontextmanager
from uuid import uuid4

from fastapi import FastAPI, Request
from fastapi.exceptions import RequestValidationError
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import Response
from starlette.exceptions import HTTPException as StarletteHTTPException

from novelforge.ai.analysis_proposal_router import router as analysis_proposal_router
from novelforge.ai.analysis_router import router as analysis_router
from novelforge.ai.context_router import router as context_router
from novelforge.ai.generation_router import router as generation_router
from novelforge.ai.tool_router import router as tool_router
from novelforge.canon.revision_router import router as revision_router
from novelforge.canon.router import router as canon_router
from novelforge.consistency.router import router as consistency_router
from novelforge.database import create_database_engine, make_session_factory
from novelforge.errors import (
    Problem,
    http_error_handler,
    problem_handler,
    validation_error_handler,
)
from novelforge.identity.router import router as identity_router
from novelforge.knowledge.router import router as knowledge_router
from novelforge.planning.router import router as planning_router
from novelforge.projects.router import router as projects_router
from novelforge.settings import Settings


def create_app(settings: Settings | None = None, engine=None) -> FastAPI:
    app_settings = settings or Settings()
    database_engine = (
        engine if engine is not None else create_database_engine(app_settings.database_url)
    )

    @asynccontextmanager
    async def lifespan(_app: FastAPI) -> AsyncIterator[None]:
        yield
        database_engine.dispose()

    application = FastAPI(
        title="NovelForge API",
        version="0.1.0",
        lifespan=lifespan,
    )
    application.state.settings = app_settings
    application.state.engine = database_engine
    application.state.session_factory = make_session_factory(database_engine)
    application.add_middleware(
        CORSMiddleware,
        allow_origins=app_settings.allowed_origins,
        allow_credentials=True,
        allow_methods=["GET", "POST", "PATCH", "DELETE", "OPTIONS"],
        allow_headers=["Authorization", "Content-Type", "X-CSRF-Token", "X-Request-ID"],
        expose_headers=["ETag", "X-NovelForge-Session"],
    )
    application.add_exception_handler(Problem, problem_handler)
    application.add_exception_handler(RequestValidationError, validation_error_handler)
    application.add_exception_handler(StarletteHTTPException, http_error_handler)

    @application.middleware("http")
    async def add_request_id(request: Request, call_next) -> Response:
        request_id = uuid4().hex
        request.state.request_id = request_id
        response = await call_next(request)
        response.headers["X-Request-ID"] = request_id
        return response

    @application.get("/health", tags=["operations"])
    def health() -> dict[str, str]:
        return {"status": "ok"}

    @application.get("/ready", tags=["operations"])
    def readiness() -> dict[str, str]:
        try:
            from sqlalchemy import text

            with database_engine.connect() as connection:
                connection.execute(text("SELECT 1"))
        except Exception as error:
            raise Problem(
                503, "SERVICE_NOT_READY", "Service not ready", "Database is unavailable."
            ) from error
        return {"status": "ready"}

    application.include_router(identity_router, prefix="/api/v1")
    application.include_router(projects_router, prefix="/api/v1")
    application.include_router(canon_router, prefix="/api/v1")
    application.include_router(consistency_router, prefix="/api/v1")
    application.include_router(revision_router, prefix="/api/v1")
    application.include_router(knowledge_router, prefix="/api/v1")
    application.include_router(context_router, prefix="/api/v1")
    application.include_router(tool_router, prefix="/api/v1")
    application.include_router(generation_router, prefix="/api/v1")
    application.include_router(analysis_router, prefix="/api/v1")
    application.include_router(analysis_proposal_router, prefix="/api/v1")
    application.include_router(planning_router, prefix="/api/v1")
    return application


app = create_app()

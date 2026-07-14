from collections.abc import AsyncIterator
from contextlib import asynccontextmanager
from uuid import UUID

from fastapi import FastAPI, Query, Request, Response, status
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse

from src.config.settings import Settings
from src.errors import ConflictError, InvalidProcessSourceError, NotFoundError
from src.infrastructure.database import Database
from src.infrastructure.executor import ProcessExecutor
from src.infrastructure.script_files import ScriptFileResolver
from src.models.job import Job, JobCreate, JobUpdate
from src.models.job_run import JobRun
from src.models.process import Process, ProcessCreate, ProcessUpdate
from src.services.job_service import JobService
from src.services.orchestrator import Orchestrator
from src.services.process_service import ProcessService


class Server:
    def __init__(self, settings: Settings) -> None:
        self._settings = settings
        self._database = Database(settings.DATABASE_URL)
        script_files = ScriptFileResolver(settings.SCRIPT_ROOT)
        self._process_service = ProcessService(self._database, script_files)
        self._job_service = JobService(self._database, self._process_service)
        executor = ProcessExecutor(
            settings.PROCESS_TIMEOUT_SECONDS,
            settings.MAX_CAPTURED_OUTPUT_BYTES,
            script_files,
        )
        self._orchestrator = Orchestrator(settings, self._job_service, executor)
        self._app = FastAPI(
            title=settings.SERVICE_NAME,
            lifespan=self._lifespan,
        )
        self._configure_middleware()
        self.register_routes()
        if settings.FRONTEND_DIR.is_dir():
            self._app.frontend(
                "/",
                directory=settings.FRONTEND_DIR,
                fallback="index.html",
            )

    @asynccontextmanager
    async def _lifespan(self, app: FastAPI) -> AsyncIterator[None]:
        await self._database.migrate()
        await self.run()
        try:
            yield
        finally:
            await self.stop()

    @property
    def app(self) -> FastAPI:
        return self._app

    def _configure_middleware(self) -> None:
        self._app.add_middleware(
            CORSMiddleware,
            allow_origins=self._settings.CORS_ORIGINS,
            allow_credentials=True,
            allow_methods=self._settings.CORS_ALLOW_METHODS,
            allow_headers=self._settings.CORS_ALLOW_HEADERS,
        )

    def register_routes(self) -> None:
        @self._app.exception_handler(NotFoundError)
        async def not_found_handler(
            request: Request,
            error: NotFoundError,
        ) -> JSONResponse:
            return JSONResponse(status_code=404, content={"detail": str(error)})

        @self._app.exception_handler(ConflictError)
        async def conflict_handler(
            request: Request,
            error: ConflictError,
        ) -> JSONResponse:
            return JSONResponse(status_code=409, content={"detail": str(error)})

        @self._app.exception_handler(InvalidProcessSourceError)
        async def invalid_process_source_handler(
            request: Request,
            error: InvalidProcessSourceError,
        ) -> JSONResponse:
            return JSONResponse(status_code=422, content={"detail": str(error)})

        if not self._settings.FRONTEND_DIR.is_dir():
            @self._app.get("/")
            async def root() -> dict[str, str]:
                return {"service": self._settings.SERVICE_NAME}

        @self._app.get("/api/health")
        async def health() -> dict[str, str]:
            database_status = "up" if await self._database.ping() else "down"
            return {
                "service": self._settings.SERVICE_NAME,
                "status": self._orchestrator.get_status(),
                "database": database_status,
            }

        @self._app.get("/api/orchestrator")
        async def orchestrator_status() -> dict[str, str]:
            return {"status": self._orchestrator.get_status()}

        @self._app.post("/api/orchestrator/start")
        async def start_orchestrator() -> dict[str, str]:
            await self.run()
            return {"status": self._orchestrator.get_status()}

        @self._app.post("/api/orchestrator/pause")
        async def pause_orchestrator() -> dict[str, str]:
            await self.pause()
            return {"status": self._orchestrator.get_status()}

        @self._app.post("/api/orchestrator/stop")
        async def stop_orchestrator() -> dict[str, str]:
            await self.stop()
            return {"status": self._orchestrator.get_status()}

        @self._app.post(
            "/api/processes",
            response_model=Process,
            status_code=status.HTTP_201_CREATED,
        )
        async def add_process(request: ProcessCreate) -> Process:
            return await self._process_service.add_process(request)

        @self._app.get("/api/processes", response_model=list[Process])
        async def list_processes() -> list[Process]:
            return await self._process_service.list_processes()

        @self._app.get(
            "/api/processes/{process_id}",
            response_model=Process,
        )
        async def get_process(process_id: UUID) -> Process:
            return await self._process_service.get_process(process_id)

        @self._app.patch(
            "/api/processes/{process_id}",
            response_model=Process,
        )
        async def update_process(
            process_id: UUID,
            request: ProcessUpdate,
        ) -> Process:
            return await self._process_service.update_process(process_id, request)

        @self._app.post(
            "/api/processes/{process_id}/enable",
            response_model=Process,
        )
        async def enable_process(process_id: UUID) -> Process:
            process = await self._process_service.enable_process(process_id)
            self._orchestrator.wake()
            return process

        @self._app.post(
            "/api/processes/{process_id}/disable",
            response_model=Process,
        )
        async def disable_process(process_id: UUID) -> Process:
            return await self._process_service.disable_process(process_id)

        @self._app.delete(
            "/api/processes/{process_id}",
            status_code=status.HTTP_204_NO_CONTENT,
        )
        async def remove_process(process_id: UUID) -> Response:
            await self._process_service.remove_process(process_id)
            return Response(status_code=status.HTTP_204_NO_CONTENT)

        @self._app.post(
            "/api/jobs",
            response_model=Job,
            status_code=status.HTTP_201_CREATED,
        )
        async def add_job(request: JobCreate) -> Job:
            job = await self._job_service.add_job(request)
            self._orchestrator.wake()
            return job

        @self._app.get("/api/jobs", response_model=list[Job])
        async def list_jobs() -> list[Job]:
            return await self._job_service.list_jobs()

        @self._app.get("/api/jobs/{job_id}", response_model=Job)
        async def get_job(job_id: UUID) -> Job:
            return await self._job_service.get_job(job_id)

        @self._app.patch("/api/jobs/{job_id}", response_model=Job)
        async def update_job(job_id: UUID, request: JobUpdate) -> Job:
            job = await self._job_service.update_job(job_id, request)
            self._orchestrator.wake()
            return job

        @self._app.post("/api/jobs/{job_id}/run-now", response_model=Job)
        async def run_job_now(job_id: UUID) -> Job:
            job = await self._job_service.run_job_now(job_id)
            self._orchestrator.wake()
            return job

        @self._app.delete(
            "/api/jobs/{job_id}",
            status_code=status.HTTP_204_NO_CONTENT,
        )
        async def remove_job(job_id: UUID) -> Response:
            await self._job_service.remove_job(job_id)
            return Response(status_code=status.HTTP_204_NO_CONTENT)

        @self._app.get("/api/runs", response_model=list[JobRun])
        async def list_runs(
            job_id: UUID | None = None,
            limit: int = Query(default=100, ge=1, le=500),
        ) -> list[JobRun]:
            return await self._job_service.list_runs(job_id, limit)

    async def run(self) -> None:
        await self._orchestrator.start()

    async def pause(self) -> None:
        await self._orchestrator.pause()

    async def stop(self) -> None:
        await self._orchestrator.stop()


def create_app(settings: Settings) -> FastAPI:
    return Server(settings).app

import asyncio
import logging
from enum import StrEnum

from src.config.settings import Settings
from src.models.job_run import JobRunStatus
from src.services.executor import ProcessExecutor, ProcessTimeoutError
from src.services.job_service import ClaimedJob, JobService

logger = logging.getLogger(__name__)


class OrchestratorStatus(StrEnum):
    INITIALISED = "initialised"
    STARTING = "starting"
    RUNNING = "running"
    PAUSED = "paused"
    STOPPING = "stopping"
    STOPPED = "stopped"


class Orchestrator:
    def __init__(
        self,
        settings: Settings,
        job_service: JobService,
        executor: ProcessExecutor,
    ) -> None:
        self._settings = settings
        self._job_service = job_service
        self._executor = executor
        self._status = OrchestratorStatus.INITIALISED
        self._heartbeat_task: asyncio.Task[None] | None = None
        self._execution_tasks: set[asyncio.Task[None]] = set()
        self._wake_event = asyncio.Event()

    async def start(self) -> None:
        if self._status is OrchestratorStatus.RUNNING:
            return
        self._status = OrchestratorStatus.STARTING
        self._status = OrchestratorStatus.RUNNING
        if self._heartbeat_task is None or self._heartbeat_task.done():
            self._heartbeat_task = asyncio.create_task(self._heartbeat())
        self._wake_event.set()

    async def pause(self) -> None:
        if self._status is OrchestratorStatus.RUNNING:
            self._status = OrchestratorStatus.PAUSED
            self._wake_event.set()

    async def stop(self) -> None:
        if self._status is OrchestratorStatus.STOPPED:
            return
        self._status = OrchestratorStatus.STOPPING
        self._wake_event.set()
        if self._heartbeat_task:
            self._heartbeat_task.cancel()
            await asyncio.gather(self._heartbeat_task, return_exceptions=True)
            self._heartbeat_task = None
        for task in self._execution_tasks:
            task.cancel()
        if self._execution_tasks:
            await asyncio.gather(*self._execution_tasks, return_exceptions=True)
            self._execution_tasks.clear()
        self._status = OrchestratorStatus.STOPPED

    def get_status(self) -> OrchestratorStatus:
        return self._status

    def wake(self) -> None:
        self._wake_event.set()

    async def _heartbeat(self) -> None:
        while self._status not in {
            OrchestratorStatus.STOPPING,
            OrchestratorStatus.STOPPED,
        }:
            if self._status is OrchestratorStatus.PAUSED:
                self._wake_event.clear()
                await self._wake_event.wait()
                continue

            self._wake_event.clear()
            try:
                await self._dispatch_pending_jobs()
            except asyncio.CancelledError:
                raise
            except Exception:
                logger.exception("orchestrator heartbeat failed")

            try:
                await asyncio.wait_for(
                    self._wake_event.wait(),
                    timeout=self._settings.HEART_BEAT_INTERVAL,
                )
            except TimeoutError:
                pass

    async def _dispatch_pending_jobs(self) -> None:
        available_slots = (
            self._settings.MAX_CONCURRENT_JOBS - len(self._execution_tasks)
        )
        if available_slots <= 0:
            return

        jobs = await self._job_service.claim_due_jobs(available_slots)
        for job in jobs:
            task = asyncio.create_task(self._execute(job))
            self._execution_tasks.add(task)
            task.add_done_callback(self._execution_finished)

    def _execution_finished(self, task: asyncio.Task[None]) -> None:
        self._execution_tasks.discard(task)
        if not task.cancelled() and (error := task.exception()) is not None:
            logger.error(
                "job execution task failed",
                exc_info=(type(error), error, error.__traceback__),
            )
        self._wake_event.set()

    async def _execute(self, claimed: ClaimedJob) -> None:
        try:
            result = await self._executor.execute(claimed.process)
            if result.return_code == 0:
                await self._job_service.finish_run(
                    claimed.job_run_id,
                    JobRunStatus.COMPLETED,
                    result.output,
                )
                return
            await self._job_service.finish_run(
                claimed.job_run_id,
                JobRunStatus.ERROR,
                result.output,
                f"process exited with code {result.return_code}",
            )
        except ProcessTimeoutError as error:
            await self._job_service.finish_run(
                claimed.job_run_id,
                JobRunStatus.ERROR,
                error.output,
                str(error),
            )
        except asyncio.CancelledError:
            await self._job_service.finish_run(
                claimed.job_run_id,
                JobRunStatus.ERROR,
                "",
                "orchestrator stopped during execution",
            )
            raise
        except Exception as error:
            await self._job_service.finish_run(
                claimed.job_run_id,
                JobRunStatus.ERROR,
                "",
                str(error),
            )

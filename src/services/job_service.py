from dataclasses import dataclass
from datetime import UTC, datetime
from uuid import UUID, uuid4

from croniter import croniter
from psycopg.errors import ForeignKeyViolation
from psycopg.rows import DictRow

from src.errors import ConflictError, NotFoundError
from src.infrastructure.database import Database
from src.models.job import Job, JobCreate, JobUpdate
from src.models.job_run import JobRun, JobRunStatus
from src.models.process import Process
from src.services.process_service import ProcessService


_JOB_SELECT = """
    SELECT
        j.job_id, j.arguments, j.recurring, j.cron, j.last_run_at, j.next_run_at,
        j.created_at, j.created_by, j.modified_at, j.modified_by, j.active,
        p.process_id AS process_process_id,
        p.type AS process_type,
        p.name AS process_name,
        p.source_kind AS process_source_kind,
        p.script AS process_script,
        p.script_path AS process_script_path,
        p.enabled AS process_enabled,
        p.created_at AS process_created_at,
        p.created_by AS process_created_by,
        p.modified_at AS process_modified_at,
        p.modified_by AS process_modified_by,
        p.last_run_at AS process_last_run_at
    FROM jobs j
    JOIN processes p ON p.process_id = j.process_id
"""

_RUN_SELECT = """
    SELECT
        r.job_run_id, r.status, r.captured_output,
        r.started_at, r.finished_at,
        e.exception,
        j.job_id, j.arguments, j.recurring, j.cron, j.last_run_at, j.next_run_at,
        j.created_at, j.created_by, j.modified_at, j.modified_by, j.active,
        p.process_id AS process_process_id,
        p.type AS process_type,
        p.name AS process_name,
        p.source_kind AS process_source_kind,
        p.script AS process_script,
        p.script_path AS process_script_path,
        p.enabled AS process_enabled,
        p.created_at AS process_created_at,
        p.created_by AS process_created_by,
        p.modified_at AS process_modified_at,
        p.modified_by AS process_modified_by,
        p.last_run_at AS process_last_run_at
    FROM job_runs r
    JOIN jobs j ON j.job_id = r.job_id
    JOIN processes p ON p.process_id = j.process_id
    LEFT JOIN job_exceptions e ON e.job_run_id = r.job_run_id
"""


@dataclass(frozen=True)
class ClaimedJob:
    job_run_id: UUID
    process: Process
    arguments: tuple[str, ...]


class JobService:
    def __init__(
        self,
        database: Database,
        process_service: ProcessService,
    ) -> None:
        self._database = database
        self._process_service = process_service

    async def add_job(self, request: JobCreate) -> Job:
        process = await self._process_service.get_process(request.process_id)
        now = datetime.now(UTC)
        next_run_at = request.next_run_at
        if next_run_at is None:
            next_run_at = self._next_run(request.cron, now) if request.cron else now

        job = Job(
            job_id=uuid4(),
            process=process,
            arguments=request.arguments,
            recurring=request.recurring,
            cron=request.cron,
            next_run_at=next_run_at,
            created_at=now,
            modified_at=now,
        )
        async with self._database.connection() as connection:
            await connection.execute(
                """
                INSERT INTO jobs (
                    job_id, process_id, arguments, recurring, cron, last_run_at,
                    next_run_at, created_at, created_by, modified_at,
                    modified_by, active
                ) VALUES (
                    %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s
                )
                """,
                (
                    job.job_id,
                    process.process_id,
                    job.arguments,
                    job.recurring,
                    job.cron,
                    job.last_run_at,
                    job.next_run_at,
                    job.created_at,
                    job.created_by,
                    job.modified_at,
                    job.modified_by,
                    job.active,
                ),
            )
        return job

    async def list_jobs(self) -> list[Job]:
        async with self._database.connection() as connection:
            cursor = await connection.execute(
                _JOB_SELECT + " ORDER BY j.created_at DESC"
            )
            rows = await cursor.fetchall()
        return [self._job_from_row(row) for row in rows]

    async def get_job(self, job_id: UUID) -> Job:
        async with self._database.connection() as connection:
            cursor = await connection.execute(
                _JOB_SELECT + " WHERE j.job_id = %s",
                (job_id,),
            )
            row = await cursor.fetchone()
        if row is None:
            raise NotFoundError("job not found")
        return self._job_from_row(row)

    async def update_job(self, job_id: UUID, request: JobUpdate) -> Job:
        job = await self.get_job(job_id)
        active = request.active if request.active is not None else job.active
        next_run_at = request.next_run_at or job.next_run_at
        if active and next_run_at is None:
            next_run_at = self._next_run(job.cron, datetime.now(UTC))

        async with self._database.connection() as connection:
            await connection.execute(
                """
                UPDATE jobs
                SET active = %s, next_run_at = %s, modified_at = %s
                WHERE job_id = %s
                """,
                (active, next_run_at, datetime.now(UTC), job_id),
            )
        return await self.get_job(job_id)

    async def run_job_now(self, job_id: UUID) -> Job:
        await self.get_job(job_id)
        async with self._database.connection() as connection:
            await connection.execute(
                """
                UPDATE jobs
                SET active = TRUE, run_requested = TRUE, modified_at = %s
                WHERE job_id = %s
                """,
                (datetime.now(UTC), job_id),
            )
        return await self.get_job(job_id)

    async def remove_job(self, job_id: UUID) -> None:
        try:
            async with self._database.connection() as connection:
                cursor = await connection.execute(
                    """
                    DELETE FROM jobs
                    WHERE job_id = %s
                    RETURNING job_id
                    """,
                    (job_id,),
                )
                row = await cursor.fetchone()
        except ForeignKeyViolation as error:
            raise ConflictError("job has run history and cannot be removed") from error
        if row is None:
            raise NotFoundError("job not found")

    async def claim_due_jobs(self, limit: int) -> list[ClaimedJob]:
        now = datetime.now(UTC)
        claimed: list[ClaimedJob] = []
        async with self._database.connection() as connection:
            cursor = await connection.execute(
                _JOB_SELECT
                + """
                    WHERE j.active
                      AND p.enabled
                      AND (j.run_requested OR j.next_run_at <= %s)
                      AND NOT EXISTS (
                          SELECT 1
                          FROM job_runs active_run
                          WHERE active_run.job_id = j.job_id
                            AND active_run.status IN ('pending', 'active')
                      )
                    ORDER BY j.next_run_at
                    FOR UPDATE OF j SKIP LOCKED
                    LIMIT %s
                """,
                (now, limit),
            )
            rows = await cursor.fetchall()

            for row in rows:
                job = self._job_from_row(row)
                job_run_id = uuid4()
                next_run_at = None
                active = False
                if job.recurring and job.cron:
                    next_run_at = self._next_run(job.cron, now)
                    active = True

                await connection.execute(
                    """
                    UPDATE jobs
                    SET last_run_at = %s, next_run_at = %s, active = %s,
                        run_requested = FALSE, modified_at = %s
                    WHERE job_id = %s
                    """,
                    (now, next_run_at, active, now, job.job_id),
                )
                await connection.execute(
                    "UPDATE processes SET last_run_at = %s WHERE process_id = %s",
                    (now, job.process.process_id),
                )
                await connection.execute(
                    """
                    INSERT INTO job_runs (
                        job_run_id, job_id, status, captured_output, started_at
                    ) VALUES (%s, %s, %s, '', %s)
                    """,
                    (job_run_id, job.job_id, JobRunStatus.ACTIVE, now),
                )
                claimed.append(
                    ClaimedJob(job_run_id, job.process, tuple(job.arguments))
                )
        return claimed

    async def finish_run(
        self,
        job_run_id: UUID,
        status: JobRunStatus,
        output: str,
        exception: str | None = None,
    ) -> None:
        now = datetime.now(UTC)
        async with self._database.connection() as connection:
            cursor = await connection.execute(
                """
                UPDATE job_runs
                SET status = %s, captured_output = %s, finished_at = %s
                WHERE job_run_id = %s
                RETURNING job_run_id
                """,
                (status, output, now, job_run_id),
            )
            if await cursor.fetchone() is None:
                raise NotFoundError("job run not found")
            if exception:
                await connection.execute(
                    """
                    INSERT INTO job_exceptions (
                        job_exception_id, job_run_id, exception, created_at
                    ) VALUES (%s, %s, %s, %s)
                    """,
                    (uuid4(), job_run_id, exception, now),
                )

    async def list_runs(
        self,
        job_id: UUID | None = None,
        limit: int = 100,
    ) -> list[JobRun]:
        parameters: tuple[object, ...]
        if job_id:
            query = _RUN_SELECT + " WHERE r.job_id = %s"
            parameters = (job_id, limit)
        else:
            query = _RUN_SELECT
            parameters = (limit,)
        query += " ORDER BY r.started_at DESC NULLS LAST LIMIT %s"

        async with self._database.connection() as connection:
            cursor = await connection.execute(query, parameters)
            rows = await cursor.fetchall()
        return [self._run_from_row(row) for row in rows]

    @staticmethod
    def _next_run(expression: str | None, base: datetime) -> datetime:
        if expression is None:
            return base
        return croniter(expression, base).get_next(datetime)

    @staticmethod
    def _process_from_row(row: DictRow) -> Process:
        if row["process_source_kind"] == "inline":
            source = {
                "kind": "inline",
                "content": row["process_script"],
            }
        else:
            source = {
                "kind": "file",
                "path": row["process_script_path"],
            }
        return Process(
            process_id=row["process_process_id"],
            type=row["process_type"],
            name=row["process_name"],
            source=source,
            enabled=row["process_enabled"],
            created_at=row["process_created_at"],
            created_by=row["process_created_by"],
            modified_at=row["process_modified_at"],
            modified_by=row["process_modified_by"],
            last_run_at=row["process_last_run_at"],
        )

    @classmethod
    def _job_from_row(cls, row: DictRow) -> Job:
        return Job(
            job_id=row["job_id"],
            process=cls._process_from_row(row),
            arguments=row["arguments"],
            recurring=row["recurring"],
            cron=row["cron"],
            last_run_at=row["last_run_at"],
            next_run_at=row["next_run_at"],
            created_at=row["created_at"],
            created_by=row["created_by"],
            modified_at=row["modified_at"],
            modified_by=row["modified_by"],
            active=row["active"],
        )

    @classmethod
    def _run_from_row(cls, row: DictRow) -> JobRun:
        return JobRun(
            job_run_id=row["job_run_id"],
            job=cls._job_from_row(row),
            status=row["status"],
            captured_output=row["captured_output"],
            started_at=row["started_at"],
            finished_at=row["finished_at"],
            exception=row["exception"],
        )

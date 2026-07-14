from datetime import UTC, datetime
from uuid import UUID, uuid4

from psycopg.errors import ForeignKeyViolation
from psycopg.rows import DictRow

from src.errors import ConflictError, NotFoundError
from src.infrastructure.database import Database
from src.infrastructure.script_files import ScriptFileResolver
from src.models.process import (
    FileProcessSource,
    InlineProcessSource,
    Process,
    ProcessCreate,
    ProcessSource,
    ProcessUpdate,
)


class ProcessService:
    def __init__(
        self,
        database: Database,
        script_files: ScriptFileResolver,
    ) -> None:
        self._database = database
        self._script_files = script_files

    async def add_process(self, request: ProcessCreate) -> Process:
        self._validate_source(request.source)
        now = datetime.now(UTC)
        process = Process(
            process_id=uuid4(),
            type=request.type,
            name=request.name.strip(),
            source=request.source,
            created_at=now,
            modified_at=now,
        )
        source_values = self._source_values(process.source)
        async with self._database.connection() as connection:
            cursor = await connection.execute(
                """
                INSERT INTO processes (
                    process_id, type, name, source_kind, script, script_path,
                    enabled, created_at, created_by, modified_at, modified_by,
                    last_run_at
                ) VALUES (
                    %(process_id)s, %(type)s, %(name)s, %(source_kind)s,
                    %(script)s, %(script_path)s, %(enabled)s, %(created_at)s,
                    %(created_by)s, %(modified_at)s, %(modified_by)s,
                    %(last_run_at)s
                )
                RETURNING *
                """,
                process.model_dump(mode="json") | source_values,
            )
            row = await cursor.fetchone()
        return self._from_row(row)

    async def list_processes(self) -> list[Process]:
        async with self._database.connection() as connection:
            cursor = await connection.execute(
                "SELECT * FROM processes ORDER BY created_at DESC"
            )
            rows = await cursor.fetchall()
        return [self._from_row(row) for row in rows]

    async def get_process(self, process_id: UUID) -> Process:
        async with self._database.connection() as connection:
            cursor = await connection.execute(
                "SELECT * FROM processes WHERE process_id = %s",
                (process_id,),
            )
            row = await cursor.fetchone()
        if row is None:
            raise NotFoundError("process not found")
        return self._from_row(row)

    async def update_process(
        self,
        process_id: UUID,
        request: ProcessUpdate,
    ) -> Process:
        changes = request.model_dump(exclude_none=True)
        if request.source is not None:
            self._validate_source(request.source)
            changes.update(self._source_values(request.source))
            del changes["source"]
        assignments = [f"{field} = %s" for field in changes]
        values = [
            value.value if hasattr(value, "value") else value
            for value in changes.values()
        ]
        assignments.append("modified_at = %s")
        values.extend((datetime.now(UTC), process_id))

        async with self._database.connection() as connection:
            cursor = await connection.execute(
                f"""
                UPDATE processes
                SET {", ".join(assignments)}
                WHERE process_id = %s
                RETURNING *
                """,
                tuple(values),
            )
            row = await cursor.fetchone()
        if row is None:
            raise NotFoundError("process not found")
        return self._from_row(row)

    async def enable_process(self, process_id: UUID) -> Process:
        return await self.update_process(
            process_id,
            ProcessUpdate(enabled=True),
        )

    async def disable_process(self, process_id: UUID) -> Process:
        return await self.update_process(
            process_id,
            ProcessUpdate(enabled=False),
        )

    async def remove_process(self, process_id: UUID) -> None:
        try:
            async with self._database.connection() as connection:
                cursor = await connection.execute(
                    """
                    DELETE FROM processes
                    WHERE process_id = %s
                    RETURNING process_id
                    """,
                    (process_id,),
                )
                row = await cursor.fetchone()
        except ForeignKeyViolation as error:
            raise ConflictError("process is used by one or more jobs") from error
        if row is None:
            raise NotFoundError("process not found")

    def _validate_source(self, source: ProcessSource) -> None:
        if isinstance(source, FileProcessSource):
            self._script_files.resolve(source.path)

    @staticmethod
    def _source_values(source: ProcessSource) -> dict[str, str | None]:
        if isinstance(source, InlineProcessSource):
            return {
                "source_kind": source.kind,
                "script": source.content,
                "script_path": None,
            }
        return {
            "source_kind": source.kind,
            "script": None,
            "script_path": source.path,
        }

    @staticmethod
    def _from_row(row: DictRow | None) -> Process:
        if row is None:
            raise NotFoundError("process not found")
        values = dict(row)
        source_kind = values.pop("source_kind")
        script = values.pop("script")
        script_path = values.pop("script_path")
        if source_kind == "inline":
            values["source"] = {"kind": "inline", "content": script}
        else:
            values["source"] = {"kind": "file", "path": script_path}
        return Process.model_validate(values)

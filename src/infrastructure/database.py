from collections.abc import AsyncIterator
from contextlib import asynccontextmanager
from pathlib import Path

from psycopg import AsyncConnection
from psycopg.rows import dict_row


class Database:
    def __init__(self, url: str) -> None:
        self._url = url
        self._migrations_dir = Path(__file__).parents[1] / "migrations"

    @asynccontextmanager
    async def connection(self) -> AsyncIterator[AsyncConnection]:
        connection = await AsyncConnection.connect(
            self._url,
            row_factory=dict_row,
        )
        async with connection:
            yield connection

    async def migrate(self) -> None:
        connection = await AsyncConnection.connect(
            self._url,
            autocommit=True,
            row_factory=dict_row,
        )
        async with connection:
            await connection.execute(
                """
                CREATE TABLE IF NOT EXISTS schema_migrations (
                    version VARCHAR(255) PRIMARY KEY,
                    applied_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
                )
                """
            )
            await connection.execute("SELECT pg_advisory_lock(747065267)")
            try:
                cursor = await connection.execute(
                    "SELECT version FROM schema_migrations"
                )
                applied = {row["version"] for row in await cursor.fetchall()}

                for migration in sorted(self._migrations_dir.glob("*.sql")):
                    if migration.name in applied:
                        continue
                    async with connection.transaction():
                        await connection.execute(migration.read_text())
                        await connection.execute(
                            "INSERT INTO schema_migrations (version) VALUES (%s)",
                            (migration.name,),
                        )
            finally:
                await connection.execute("SELECT pg_advisory_unlock(747065267)")

    async def ping(self) -> bool:
        try:
            async with self.connection() as connection:
                await connection.execute("SELECT 1")
            return True
        except Exception:
            return False

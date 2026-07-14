import asyncio
from datetime import UTC, datetime
from pathlib import Path
from uuid import UUID

from fastapi.testclient import TestClient
from psycopg import AsyncConnection

from src.config.settings import Settings
from src.server import create_app


DATABASE_URL = (
    "postgresql://dark_orchestrator:dark_orchestrator@"
    "localhost:54329/dark_orchestrator_test"
)
PROCESS_ID = UUID("9cd60ea4-b7d0-473d-93a7-1b95462d9a9b")


async def seed_v1_inline_process() -> None:
    migration_path = Path(__file__).parents[1] / "src/migrations/001_initial.sql"
    migration = migration_path.read_text()
    now = datetime.now(UTC)
    connection = await AsyncConnection.connect(DATABASE_URL)
    async with connection:
        await connection.execute(
            """
            CREATE TABLE schema_migrations (
                version VARCHAR(255) PRIMARY KEY,
                applied_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
            )
            """
        )
        await connection.execute(migration)
        await connection.execute(
            "INSERT INTO schema_migrations (version) VALUES ('001_initial.sql')"
        )
        await connection.execute(
            """
            INSERT INTO processes (
                process_id, type, name, script, enabled, created_at,
                created_by, modified_at, modified_by
            ) VALUES (%s, 'python', 'Existing inline', %s, TRUE, %s,
                      'system', %s, 'system')
            """,
            (PROCESS_ID, "print('preserved')", now, now),
        )


def test_existing_inline_process_is_preserved_by_the_source_migration() -> None:
    # Arrange
    asyncio.run(seed_v1_inline_process())
    settings = Settings(DATABASE_URL=DATABASE_URL)

    # Act
    with TestClient(create_app(settings)) as client:
        response = client.get(f"/api/processes/{PROCESS_ID}")

    # Assert
    assert response.status_code == 200
    assert response.json()["source"] == {
        "kind": "inline",
        "content": "print('preserved')",
    }

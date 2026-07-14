import asyncio

import pytest
from psycopg import AsyncConnection


TEST_DATABASE_URL = (
    "postgresql://dark_orchestrator:dark_orchestrator@"
    "localhost:54329/dark_orchestrator_test"
)


async def reset_test_database() -> None:
    connection = await AsyncConnection.connect(TEST_DATABASE_URL, autocommit=True)
    async with connection:
        await connection.execute("DROP SCHEMA public CASCADE")
        await connection.execute("CREATE SCHEMA public")


@pytest.fixture(autouse=True)
def clean_database() -> None:
    asyncio.run(reset_test_database())

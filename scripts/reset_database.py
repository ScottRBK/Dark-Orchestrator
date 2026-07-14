import argparse
import asyncio

from psycopg import AsyncConnection


DATABASE_URLS = {
    "test": (
        "postgresql://dark_orchestrator:dark_orchestrator@"
        "localhost:54329/dark_orchestrator_test"
    ),
    "e2e": (
        "postgresql://dark_orchestrator:dark_orchestrator@"
        "localhost:54329/dark_orchestrator_e2e"
    ),
}


async def reset_database(name: str) -> None:
    connection = await AsyncConnection.connect(
        DATABASE_URLS[name],
        autocommit=True,
    )
    async with connection:
        await connection.execute("DROP SCHEMA public CASCADE")
        await connection.execute("CREATE SCHEMA public")


def main() -> None:
    parser = argparse.ArgumentParser(description="Reset a Dark Orchestrator test database")
    parser.add_argument("database", choices=DATABASE_URLS)
    arguments = parser.parse_args()
    asyncio.run(reset_database(arguments.database))


if __name__ == "__main__":
    main()

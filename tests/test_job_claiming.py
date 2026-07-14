from time import monotonic, sleep

from fastapi.testclient import TestClient

from src.config.settings import Settings
from src.server import create_app


DATABASE_URL = (
    "postgresql://dark_orchestrator:dark_orchestrator@"
    "localhost:54329/dark_orchestrator_test"
)


def test_two_orchestrators_execute_a_due_job_only_once() -> None:
    # Arrange
    settings = Settings(
        DATABASE_URL=DATABASE_URL,
        HEART_BEAT_INTERVAL=0.05,
    )

    with (
        TestClient(create_app(settings)) as first_client,
        TestClient(create_app(settings)) as second_client,
    ):
        process = first_client.post(
            "/api/processes",
            json={
                "name": "Exactly once",
                "type": "python",
                "source": {
                    "kind": "inline",
                    "content": "print('claimed')",
                },
            },
        ).json()

        # Act
        job = first_client.post(
            "/api/jobs",
            json={"process_id": process["process_id"]},
        ).json()
        deadline = monotonic() + 3
        runs = []
        while monotonic() < deadline:
            runs = second_client.get(f"/api/runs?job_id={job['job_id']}").json()
            if runs and runs[0]["status"] == "completed":
                break
            sleep(0.05)
        sleep(0.15)
        runs = first_client.get(f"/api/runs?job_id={job['job_id']}").json()

        # Assert
        assert len(runs) == 1
        assert runs[0]["status"] == "completed"
        assert runs[0]["captured_output"] == "claimed\n"

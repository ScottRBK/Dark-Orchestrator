from datetime import UTC, datetime, timedelta

from fastapi.testclient import TestClient

from src.config.settings import Settings
from src.server import create_app


DATABASE_URL = (
    "postgresql://dark_orchestrator:dark_orchestrator@"
    "localhost:54329/dark_orchestrator_test"
)


def test_processes_and_jobs_remain_available_after_server_restart() -> None:
    # Arrange
    settings = Settings(DATABASE_URL=DATABASE_URL)
    with TestClient(create_app(settings)) as first_client:
        process = first_client.post(
            "/api/processes",
            json={
                "name": "Persistent process",
                "type": "python",
                "source": {
                    "kind": "inline",
                    "content": "print('still here')",
                },
            },
        ).json()
        job = first_client.post(
            "/api/jobs",
            json={
                "process_id": process["process_id"],
                "next_run_at": (datetime.now(UTC) + timedelta(days=1)).isoformat(),
            },
        ).json()

    # Act
    with TestClient(create_app(settings)) as restarted_client:
        stored_process = restarted_client.get(
            f"/api/processes/{process['process_id']}"
        )
        stored_job = restarted_client.get(f"/api/jobs/{job['job_id']}")

        # Assert
        assert stored_process.status_code == 200
        assert stored_process.json()["name"] == "Persistent process"
        assert stored_job.status_code == 200
        assert stored_job.json()["process"]["process_id"] == process["process_id"]

from time import monotonic, sleep

from fastapi.testclient import TestClient

from src.config.settings import Settings
from src.server import create_app


DATABASE_URL = (
    "postgresql://dark_orchestrator:dark_orchestrator@"
    "localhost:54329/dark_orchestrator_test"
)


def test_user_can_pause_and_resume_job_dispatch() -> None:
    # Arrange
    settings = Settings(
        DATABASE_URL=DATABASE_URL,
        HEART_BEAT_INTERVAL=0.05,
    )

    with TestClient(create_app(settings)) as client:
        pause_response = client.post("/api/orchestrator/pause")
        assert pause_response.status_code == 200
        assert pause_response.json() == {"status": "paused"}

        process = client.post(
            "/api/processes",
            json={
                "name": "Paused process",
                "type": "python",
                "source": {
                    "kind": "inline",
                    "content": "print('resumed')",
                },
            },
        ).json()
        job = client.post(
            "/api/jobs",
            json={"process_id": process["process_id"]},
        ).json()

        # Act
        sleep(0.15)
        paused_runs = client.get(f"/api/runs?job_id={job['job_id']}").json()
        resume_response = client.post("/api/orchestrator/start")

        deadline = monotonic() + 3
        resumed_runs = []
        while monotonic() < deadline:
            resumed_runs = client.get(
                f"/api/runs?job_id={job['job_id']}"
            ).json()
            if resumed_runs and resumed_runs[0]["status"] == "completed":
                break
            sleep(0.05)

        # Assert
        assert paused_runs == []
        assert resume_response.status_code == 200
        assert resume_response.json() == {"status": "running"}
        assert resumed_runs[0]["captured_output"] == "resumed\n"
        status_response = client.get("/api/orchestrator")
        assert status_response.json() == {"status": "running"}

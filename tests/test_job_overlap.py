from datetime import datetime
from time import monotonic, sleep

from fastapi.testclient import TestClient

from src.config.settings import Settings
from src.server import create_app


DATABASE_URL = (
    "postgresql://dark_orchestrator:dark_orchestrator@"
    "localhost:54329/dark_orchestrator_test"
)


def test_run_now_queues_behind_an_existing_run_of_the_same_job() -> None:
    # Arrange
    settings = Settings(
        DATABASE_URL=DATABASE_URL,
        HEART_BEAT_INTERVAL=0.02,
        MAX_CONCURRENT_JOBS=2,
    )

    with TestClient(create_app(settings)) as client:
        process = client.post(
            "/api/processes",
            json={
                "name": "No overlap",
                "type": "python",
                "source": {
                    "kind": "inline",
                    "content": "import time; time.sleep(0.3); print('done')",
                },
            },
        ).json()
        job = client.post(
            "/api/jobs",
            json={"process_id": process["process_id"]},
        ).json()

        deadline = monotonic() + 3
        first_run = None
        while monotonic() < deadline:
            runs = client.get(f"/api/runs?job_id={job['job_id']}").json()
            if runs and runs[0]["status"] == "active":
                first_run = runs[0]
                break
            sleep(0.02)
        assert first_run is not None

        # Act
        run_now_response = client.post(f"/api/jobs/{job['job_id']}/run-now")
        deadline = monotonic() + 3
        runs = []
        while monotonic() < deadline:
            runs = client.get(f"/api/runs?job_id={job['job_id']}").json()
            if len(runs) == 2 and all(
                run["status"] in {"completed", "error"} for run in runs
            ):
                break
            sleep(0.03)

        # Assert
        assert run_now_response.status_code == 200
        assert [run["status"] for run in runs] == ["completed", "completed"]
        newest, oldest = runs
        first_finished = datetime.fromisoformat(
            oldest["finished_at"].replace("Z", "+00:00")
        )
        second_started = datetime.fromisoformat(
            newest["started_at"].replace("Z", "+00:00")
        )
        assert second_started >= first_finished

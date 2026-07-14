from datetime import datetime
from time import monotonic, sleep

from fastapi.testclient import TestClient

from src.config.settings import Settings
from src.server import create_app


DATABASE_URL = (
    "postgresql://dark_orchestrator:dark_orchestrator@"
    "localhost:54329/dark_orchestrator_test"
)


def test_scheduler_refills_a_free_execution_slot_without_waiting_for_long_jobs() -> None:
    # Arrange
    settings = Settings(
        DATABASE_URL=DATABASE_URL,
        HEART_BEAT_INTERVAL=0.02,
        MAX_CONCURRENT_JOBS=2,
    )

    with TestClient(create_app(settings)) as client:
        client.post("/api/orchestrator/pause")
        scripts = [
            ("Long process", "import time; time.sleep(0.5); print('long')"),
            ("Quick process one", "print('quick one')"),
            ("Quick process two", "print('quick two')"),
        ]
        job_ids = []
        for name, script in scripts:
            process = client.post(
                "/api/processes",
                json={
                    "name": name,
                    "type": "python",
                    "source": {"kind": "inline", "content": script},
                },
            ).json()
            job = client.post(
                "/api/jobs",
                json={"process_id": process["process_id"]},
            ).json()
            job_ids.append(job["job_id"])

        # Act
        client.post("/api/orchestrator/start")
        deadline = monotonic() + 3
        runs_by_job: dict[str, dict] = {}
        while monotonic() < deadline:
            for job_id in job_ids:
                runs = client.get(f"/api/runs?job_id={job_id}").json()
                if runs and runs[0]["status"] == "completed":
                    runs_by_job[job_id] = runs[0]
            if len(runs_by_job) == 3:
                break
            sleep(0.03)

        # Assert
        assert len(runs_by_job) == 3
        long_finished = datetime.fromisoformat(
            runs_by_job[job_ids[0]]["finished_at"].replace("Z", "+00:00")
        )
        second_quick_finished = datetime.fromisoformat(
            runs_by_job[job_ids[2]]["finished_at"].replace("Z", "+00:00")
        )
        assert second_quick_finished < long_finished

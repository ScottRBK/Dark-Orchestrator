from datetime import UTC, datetime, timedelta
from time import monotonic, sleep

from fastapi.testclient import TestClient

from src.config.settings import Settings
from src.server import create_app


DATABASE_URL = (
    "postgresql://dark_orchestrator:dark_orchestrator@"
    "localhost:54329/dark_orchestrator_test"
)


def wait_for_completed_runs(
    client: TestClient,
    job_id: str,
    count: int,
) -> list[dict]:
    deadline = monotonic() + 3
    runs = []
    while monotonic() < deadline:
        runs = client.get(f"/api/runs?job_id={job_id}").json()
        completed = [run for run in runs if run["status"] == "completed"]
        if len(completed) >= count:
            return completed
        sleep(0.05)
    raise AssertionError(f"expected {count} completed runs, received {runs}")


def test_user_can_control_recurring_jobs_and_run_them_on_demand() -> None:
    # Arrange
    settings = Settings(
        DATABASE_URL=DATABASE_URL,
        HEART_BEAT_INTERVAL=0.05,
    )

    with TestClient(create_app(settings)) as client:
        client.post("/api/orchestrator/pause")
        process = client.post(
            "/api/processes",
            json={
                "name": "Recurring process",
                "type": "python",
                "source": {
                    "kind": "inline",
                    "content": "print('tick')",
                },
            },
        ).json()
        job = client.post(
            "/api/jobs",
            json={
                "process_id": process["process_id"],
                "recurring": True,
                "cron": "*/5 * * * *",
                "next_run_at": datetime.now(UTC).isoformat(),
            },
        ).json()

        # Act
        deactivate_response = client.patch(
            f"/api/jobs/{job['job_id']}",
            json={"active": False},
        )
        client.post("/api/orchestrator/start")
        sleep(0.15)
        inactive_runs = client.get(f"/api/runs?job_id={job['job_id']}").json()

        activate_response = client.patch(
            f"/api/jobs/{job['job_id']}",
            json={"active": True},
        )
        first_runs = wait_for_completed_runs(client, job["job_id"], 1)
        first_stored_job = client.get(f"/api/jobs/{job['job_id']}").json()

        run_now_response = client.post(f"/api/jobs/{job['job_id']}/run-now")
        second_runs = wait_for_completed_runs(client, job["job_id"], 2)

        future_process = client.post(
            "/api/processes",
            json={
                "name": "Future process",
                "type": "bash",
                "source": {
                    "kind": "inline",
                    "content": "true",
                },
            },
        ).json()
        future_job = client.post(
            "/api/jobs",
            json={
                "process_id": future_process["process_id"],
                "next_run_at": (datetime.now(UTC) + timedelta(days=1)).isoformat(),
            },
        ).json()
        delete_response = client.delete(f"/api/jobs/{future_job['job_id']}")

        # Assert
        assert deactivate_response.json()["active"] is False
        assert inactive_runs == []
        assert activate_response.json()["active"] is True
        assert first_runs[0]["captured_output"] == "tick\n"
        assert first_stored_job["active"] is True
        assert first_stored_job["next_run_at"] is not None
        assert run_now_response.status_code == 200
        assert len(second_runs) == 2
        assert delete_response.status_code == 204
        assert client.get(f"/api/jobs/{future_job['job_id']}").status_code == 404

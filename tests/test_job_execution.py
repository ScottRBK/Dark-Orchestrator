import os
import signal
from time import monotonic, sleep

from fastapi.testclient import TestClient

from src.config.settings import Settings
from src.server import create_app


DATABASE_URL = (
    "postgresql://dark_orchestrator:dark_orchestrator@"
    "localhost:54329/dark_orchestrator_test"
)


def wait_for_run(client: TestClient, job_id: str) -> dict:
    deadline = monotonic() + 3
    runs = []
    while monotonic() < deadline:
        response = client.get(f"/api/runs?job_id={job_id}")
        assert response.status_code == 200
        runs = response.json()
        if runs and runs[0]["status"] in {"completed", "error"}:
            return runs[0]
        sleep(0.05)
    raise AssertionError(f"job {job_id} did not finish; last runs: {runs}")


def test_user_can_schedule_a_python_process_and_read_its_output() -> None:
    # Arrange
    settings = Settings(
        DATABASE_URL=DATABASE_URL,
        HEART_BEAT_INTERVAL=0.05,
    )

    with TestClient(create_app(settings)) as client:
        process_response = client.post(
            "/api/processes",
            json={
                "name": "Welcome lead",
                "type": "python",
                "source": {
                    "kind": "inline",
                    "content": "print('dark business is online')",
                },
            },
        )
        assert process_response.status_code == 201
        process = process_response.json()

        # Act
        job_response = client.post(
            "/api/jobs",
            json={"process_id": process["process_id"]},
        )
        assert job_response.status_code == 201
        job = job_response.json()

        run = wait_for_run(client, job["job_id"])

        # Assert
        assert run["status"] == "completed"
        assert run["captured_output"] == "dark business is online\n"
        assert run["finished_at"] is not None

        stored_job = client.get(f"/api/jobs/{job['job_id']}").json()
        assert stored_job["active"] is False
        assert stored_job["last_run_at"] is not None


def test_timed_out_process_keeps_its_output_and_scheduler_recovers() -> None:
    # Arrange
    settings = Settings(
        DATABASE_URL=DATABASE_URL,
        HEART_BEAT_INTERVAL=0.05,
        PROCESS_TIMEOUT_SECONDS=0.05,
    )

    with TestClient(create_app(settings)) as client:
        slow_process = client.post(
            "/api/processes",
            json={
                "name": "Slow agent",
                "type": "bash",
                "source": {
                    "kind": "inline",
                    "content": "printf 'agent started\\n'; sleep 1",
                },
            },
        ).json()
        slow_job = client.post(
            "/api/jobs",
            json={"process_id": slow_process["process_id"]},
        ).json()

        # Act
        failed_run = wait_for_run(client, slow_job["job_id"])

        healthy_process = client.post(
            "/api/processes",
            json={
                "name": "Healthy agent",
                "type": "python",
                "source": {
                    "kind": "inline",
                    "content": "print('scheduler recovered')",
                },
            },
        ).json()
        healthy_job = client.post(
            "/api/jobs",
            json={"process_id": healthy_process["process_id"]},
        ).json()
        healthy_run = wait_for_run(client, healthy_job["job_id"])

        # Assert
        assert failed_run["status"] == "error"
        assert failed_run["captured_output"] == "agent started\n"
        assert "exceeded 0.05 seconds" in failed_run["exception"]
        assert healthy_run["status"] == "completed"
        assert healthy_run["captured_output"] == "scheduler recovered\n"


def test_timed_out_process_does_not_leave_child_processes_running() -> None:
    # Arrange
    settings = Settings(
        DATABASE_URL=DATABASE_URL,
        HEART_BEAT_INTERVAL=0.05,
        PROCESS_TIMEOUT_SECONDS=0.05,
    )

    with TestClient(create_app(settings)) as client:
        process = client.post(
            "/api/processes",
            json={
                "name": "Process tree",
                "type": "bash",
                "source": {
                    "kind": "inline",
                    "content": "sleep 10 & child=$!; echo $child; wait",
                },
            },
        ).json()
        job = client.post(
            "/api/jobs",
            json={"process_id": process["process_id"]},
        ).json()

        # Act
        run = wait_for_run(client, job["job_id"])
        child_pid = int(run["captured_output"].strip())
        try:
            os.kill(child_pid, 0)
            child_is_alive = True
        except ProcessLookupError:
            child_is_alive = False

        if child_is_alive:
            os.kill(child_pid, signal.SIGKILL)

        # Assert
        assert run["status"] == "error"
        assert child_is_alive is False


def test_large_process_output_is_truncated_to_the_configured_limit() -> None:
    # Arrange
    settings = Settings(
        DATABASE_URL=DATABASE_URL,
        HEART_BEAT_INTERVAL=0.05,
        MAX_CAPTURED_OUTPUT_BYTES=64,
    )

    with TestClient(create_app(settings)) as client:
        process = client.post(
            "/api/processes",
            json={
                "name": "Noisy process",
                "type": "python",
                "source": {
                    "kind": "inline",
                    "content": "import sys; sys.stdout.write('x' * 200)",
                },
            },
        ).json()

        # Act
        job = client.post(
            "/api/jobs",
            json={"process_id": process["process_id"]},
        ).json()
        run = wait_for_run(client, job["job_id"])

        # Assert
        expected_output = ("x" * 44) + "\n[output truncated]\n"
        assert run["status"] == "completed"
        assert run["captured_output"] == expected_output
        assert len(run["captured_output"].encode()) == 64

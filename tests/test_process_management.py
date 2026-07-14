from time import monotonic, sleep

from fastapi.testclient import TestClient

from src.config.settings import Settings
from src.server import create_app


DATABASE_URL = (
    "postgresql://dark_orchestrator:dark_orchestrator@"
    "localhost:54329/dark_orchestrator_test"
)


def test_user_can_edit_disable_enable_and_remove_processes() -> None:
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
                "name": "Draft process",
                "type": "python",
                "source": {
                    "kind": "inline",
                    "content": "print('managed')",
                },
            },
        ).json()
        process_id = process["process_id"]

        # Act
        update_response = client.patch(
            f"/api/processes/{process_id}",
            json={"name": "Managed process"},
        )
        disable_response = client.post(f"/api/processes/{process_id}/disable")
        job = client.post(
            "/api/jobs",
            json={"process_id": process_id},
        ).json()
        client.post("/api/orchestrator/start")
        sleep(0.15)
        runs_while_disabled = client.get(
            f"/api/runs?job_id={job['job_id']}"
        ).json()

        enable_response = client.post(f"/api/processes/{process_id}/enable")
        deadline = monotonic() + 3
        runs_after_enable = []
        while monotonic() < deadline:
            runs_after_enable = client.get(
                f"/api/runs?job_id={job['job_id']}"
            ).json()
            if runs_after_enable:
                break
            sleep(0.05)

        disposable = client.post(
            "/api/processes",
            json={
                "name": "Disposable",
                "type": "bash",
                "source": {
                    "kind": "inline",
                    "content": "true",
                },
            },
        ).json()
        delete_response = client.delete(
            f"/api/processes/{disposable['process_id']}"
        )

        # Assert
        assert update_response.status_code == 200
        assert update_response.json()["name"] == "Managed process"
        assert disable_response.json()["enabled"] is False
        assert runs_while_disabled == []
        assert enable_response.json()["enabled"] is True
        assert runs_after_enable[0]["status"] in {"active", "completed"}
        assert delete_response.status_code == 204
        missing_response = client.get(
            f"/api/processes/{disposable['process_id']}"
        )
        assert missing_response.status_code == 404

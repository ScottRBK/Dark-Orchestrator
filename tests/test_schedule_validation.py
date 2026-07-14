from fastapi.testclient import TestClient

from src.config.settings import Settings
from src.server import create_app


DATABASE_URL = (
    "postgresql://dark_orchestrator:dark_orchestrator@"
    "localhost:54329/dark_orchestrator_test"
)


def test_user_receives_clear_validation_for_invalid_schedules() -> None:
    # Arrange
    settings = Settings(DATABASE_URL=DATABASE_URL)

    with TestClient(create_app(settings)) as client:
        process = client.post(
            "/api/processes",
            json={
                "name": "Validated process",
                "type": "bash",
                "source": {
                    "kind": "inline",
                    "content": "true",
                },
            },
        ).json()

        # Act
        impossible_cron = client.post(
            "/api/jobs",
            json={
                "process_id": process["process_id"],
                "recurring": True,
                "cron": "0 0 31 2 *",
            },
        )
        naive_datetime = client.post(
            "/api/jobs",
            json={
                "process_id": process["process_id"],
                "next_run_at": "2026-07-14T09:00:00",
            },
        )
        mismatched_cron = client.post(
            "/api/jobs",
            json={
                "process_id": process["process_id"],
                "recurring": False,
                "cron": "0 9 * * *",
            },
        )
        six_field_cron = client.post(
            "/api/jobs",
            json={
                "process_id": process["process_id"],
                "recurring": True,
                "cron": "*/5 * * * * *",
            },
        )

        # Assert
        assert impossible_cron.status_code == 422
        assert "can never run" in impossible_cron.text
        assert naive_datetime.status_code == 422
        assert "timezone" in naive_datetime.text
        assert mismatched_cron.status_code == 422
        assert "one-off jobs" in mismatched_cron.text
        assert six_field_cron.status_code == 422
        assert "five fields" in six_field_cron.text

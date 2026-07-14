from datetime import UTC, datetime, timedelta

from fastapi.testclient import TestClient

from src.config.settings import Settings
from src.server import create_app


DATABASE_URL = (
    "postgresql://dark_orchestrator:dark_orchestrator@"
    "localhost:54329/dark_orchestrator_test"
)


def test_partial_updates_reject_null_values_instead_of_silently_ignoring_them() -> None:
    # Arrange
    settings = Settings(DATABASE_URL=DATABASE_URL)

    with TestClient(create_app(settings)) as client:
        process = client.post(
            "/api/processes",
            json={
                "name": "Not nullable",
                "type": "bash",
                "source": {"kind": "inline", "content": "true"},
            },
        ).json()
        job = client.post(
            "/api/jobs",
            json={
                "process_id": process["process_id"],
                "next_run_at": (datetime.now(UTC) + timedelta(days=1)).isoformat(),
            },
        ).json()

        # Act
        process_response = client.patch(
            f"/api/processes/{process['process_id']}",
            json={"name": None},
        )
        job_response = client.patch(
            f"/api/jobs/{job['job_id']}",
            json={"active": None},
        )

        # Assert
        assert process_response.status_code == 422
        assert "cannot be null" in process_response.text
        assert job_response.status_code == 422
        assert "cannot be null" in job_response.text

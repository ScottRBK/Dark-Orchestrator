import re
from pathlib import Path

from fastapi.testclient import TestClient

from src.config.settings import Settings
from src.server import create_app


DATABASE_URL = (
    "postgresql://dark_orchestrator:dark_orchestrator@"
    "localhost:54329/dark_orchestrator_test"
)
FRONTEND_DIR = Path(__file__).parents[1] / "web" / "dist"


def test_browser_receives_the_built_dashboard_without_hiding_api_routes() -> None:
    # Arrange
    settings = Settings(
        DATABASE_URL=DATABASE_URL,
        FRONTEND_DIR=FRONTEND_DIR,
    )

    with TestClient(create_app(settings)) as client:
        # Act
        frontend_response = client.get("/")
        api_response = client.get("/api/orchestrator")

        asset_match = re.search(r'src="(/assets/[^"]+\.js)"', frontend_response.text)
        asset_response = client.get(asset_match.group(1)) if asset_match else None

        # Assert
        assert frontend_response.status_code == 200
        assert "Dark Orchestrator" in frontend_response.text
        assert asset_response is not None
        assert asset_response.status_code == 200
        assert "javascript" in asset_response.headers["content-type"]
        assert api_response.status_code == 200
        assert api_response.json()["status"] == "running"

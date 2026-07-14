from pathlib import Path
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
        runs = client.get(f"/api/runs?job_id={job_id}").json()
        if runs and runs[0]["status"] in {"completed", "error"}:
            return runs[0]
        sleep(0.05)
    raise AssertionError(f"job {job_id} did not finish; last runs: {runs}")


def test_user_can_create_an_inline_process_source() -> None:
    # Arrange
    settings = Settings(DATABASE_URL=DATABASE_URL)
    source = {
        "kind": "inline",
        "content": "print('stored in Dark')",
    }

    with TestClient(create_app(settings)) as client:
        # Act
        response = client.post(
            "/api/processes",
            json={
                "name": "Inline process",
                "type": "python",
                "source": source,
            },
        )

        # Assert
        assert response.status_code == 201
        assert response.json()["source"] == source
        assert "script" not in response.json()


def test_user_can_execute_a_process_from_a_file_source(tmp_path: Path) -> None:
    # Arrange
    workflow_dir = tmp_path / "workflows"
    workflow_dir.mkdir()
    script_path = workflow_dir / "welcome.py"
    script_path.write_text(
        "from pathlib import Path\n"
        "print(Path('message.txt').read_text().strip())\n"
    )
    (tmp_path / "message.txt").write_text("executed from a host file\n")
    settings = Settings(
        DATABASE_URL=DATABASE_URL,
        HEART_BEAT_INTERVAL=0.05,
        SCRIPT_ROOT=tmp_path,
    )
    source = {"kind": "file", "path": "workflows/welcome.py"}

    with TestClient(create_app(settings)) as client:
        process_response = client.post(
            "/api/processes",
            json={
                "name": "File process",
                "type": "python",
                "source": source,
            },
        )
        assert process_response.status_code == 201
        process = process_response.json()

        # Act
        job = client.post(
            "/api/jobs",
            json={"process_id": process["process_id"]},
        ).json()
        run = wait_for_run(client, job["job_id"])

        # Assert
        assert process["source"] == source
        assert run["status"] == "completed"
        assert run["captured_output"] == "executed from a host file\n"


def test_file_process_source_must_be_readable(tmp_path: Path) -> None:
    # Arrange
    script_path = tmp_path / "private.py"
    script_path.write_text("print('private')\n")
    script_path.chmod(0)
    settings = Settings(DATABASE_URL=DATABASE_URL, SCRIPT_ROOT=tmp_path)

    with TestClient(create_app(settings)) as client:
        # Act
        response = client.post(
            "/api/processes",
            json={
                "name": "Unreadable source",
                "type": "python",
                "source": {"kind": "file", "path": "private.py"},
            },
        )

        # Assert
        assert response.status_code == 422
        assert "not readable" in response.text


def test_file_process_source_cannot_escape_or_reference_an_invalid_file(
    tmp_path: Path,
) -> None:
    # Arrange
    script_root = tmp_path / "scripts"
    script_root.mkdir()
    outside_script = tmp_path / "outside.py"
    outside_script.write_text("print('outside')\n")
    (script_root / "directory.py").mkdir()
    (script_root / "linked.py").symlink_to(outside_script)
    settings = Settings(DATABASE_URL=DATABASE_URL, SCRIPT_ROOT=script_root)
    invalid_sources = [
        ("../outside.py", "parent-directory traversal"),
        (str(outside_script), "relative to the configured script root"),
        ("missing.py", "does not exist"),
        ("directory.py", "not a file"),
        ("linked.py", "inside the configured script root"),
    ]

    with TestClient(create_app(settings)) as client:
        # Act
        responses = [
            client.post(
                "/api/processes",
                json={
                    "name": f"Invalid {index}",
                    "type": "python",
                    "source": {"kind": "file", "path": path},
                },
            )
            for index, (path, _) in enumerate(invalid_sources)
        ]

        # Assert
        for response, (_, expected_error) in zip(
            responses,
            invalid_sources,
            strict=True,
        ):
            assert response.status_code == 422
            assert expected_error in response.text


def test_file_source_is_revalidated_before_every_run(tmp_path: Path) -> None:
    # Arrange
    script_path = tmp_path / "temporary.py"
    script_path.write_text("print('temporary')\n")
    settings = Settings(
        DATABASE_URL=DATABASE_URL,
        HEART_BEAT_INTERVAL=0.05,
        SCRIPT_ROOT=tmp_path,
    )

    with TestClient(create_app(settings)) as client:
        client.post("/api/orchestrator/pause")
        process = client.post(
            "/api/processes",
            json={
                "name": "Temporary file",
                "type": "python",
                "source": {"kind": "file", "path": "temporary.py"},
            },
        ).json()
        job = client.post(
            "/api/jobs",
            json={"process_id": process["process_id"]},
        ).json()

        # Act
        script_path.unlink()
        client.post("/api/orchestrator/start")
        run = wait_for_run(client, job["job_id"])

        # Assert
        assert run["status"] == "error"
        assert run["captured_output"] == ""
        assert "script file does not exist: temporary.py" == run["exception"]


def test_user_can_change_an_inline_process_to_a_file_source(tmp_path: Path) -> None:
    # Arrange
    script_path = tmp_path / "replacement.sh"
    script_path.write_text("printf 'replacement source\\n'\n")
    settings = Settings(
        DATABASE_URL=DATABASE_URL,
        HEART_BEAT_INTERVAL=0.05,
        SCRIPT_ROOT=tmp_path,
    )

    with TestClient(create_app(settings)) as client:
        client.post("/api/orchestrator/pause")
        process = client.post(
            "/api/processes",
            json={
                "name": "Replace source",
                "type": "bash",
                "source": {"kind": "inline", "content": "printf 'old\\n'"},
            },
        ).json()

        # Act
        update_response = client.patch(
            f"/api/processes/{process['process_id']}",
            json={
                "source": {"kind": "file", "path": "replacement.sh"},
            },
        )
        job = client.post(
            "/api/jobs",
            json={"process_id": process["process_id"]},
        ).json()
        client.post("/api/orchestrator/start")
        run = wait_for_run(client, job["job_id"])

        # Assert
        assert update_response.status_code == 200
        assert update_response.json()["source"] == {
            "kind": "file",
            "path": "replacement.sh",
        }
        assert run["status"] == "completed"
        assert run["captured_output"] == "replacement source\n"

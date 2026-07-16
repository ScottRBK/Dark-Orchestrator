import json
import os
import subprocess
from datetime import UTC, datetime, timedelta
from pathlib import Path
from time import monotonic, sleep


REPOSITORY_ROOT = Path(__file__).parents[2]
CLI = REPOSITORY_ROOT / "dark-orchestrator"


def run_cli(
    *arguments: str,
    env: dict[str, str] | None = None,
) -> subprocess.CompletedProcess[str]:
    return subprocess.run(
        [str(CLI), *arguments],
        cwd=REPOSITORY_ROOT,
        capture_output=True,
        text=True,
        check=False,
        env={**os.environ, **(env or {})},
    )


def test_cli_exposes_discoverable_help() -> None:
    # Arrange
    arguments = ["--help"]

    # Act
    result = run_cli(*arguments)

    # Assert
    assert result.returncode == 0
    assert "Command-line client for Dark Orchestrator" in result.stdout
    assert "{health,orchestrator,process,job,run}" in result.stdout
    assert result.stderr == ""


def test_cli_can_be_symlinked_onto_path(tmp_path: Path) -> None:
    # Arrange
    installed_cli = tmp_path / "dark-orchestrator"
    installed_cli.symlink_to(CLI)

    # Act
    result = subprocess.run(
        [str(installed_cli), "--help"],
        cwd=tmp_path,
        capture_output=True,
        text=True,
        check=False,
    )

    # Assert
    assert result.returncode == 0, result.stderr
    assert "Command-line client for Dark Orchestrator" in result.stdout


def test_user_can_check_service_health(live_server_url: str) -> None:
    # Arrange
    expected_health = {
        "service": "Dark Orchestrator",
        "status": "running",
        "database": "up",
    }

    # Act
    result = run_cli("--url", live_server_url, "health")

    # Assert
    assert result.returncode == 0, result.stderr
    assert json.loads(result.stdout) == expected_health
    assert result.stderr == ""


def test_user_can_select_the_server_with_an_environment_variable(
    live_server_url: str,
) -> None:
    # Arrange
    environment = {"DARK_ORCH_API_URL": live_server_url}

    # Act
    result = run_cli("orchestrator", "status", env=environment)

    # Assert
    assert result.returncode == 0, result.stderr
    assert json.loads(result.stdout) == {"status": "running"}
    assert result.stderr == ""


def test_user_can_inspect_and_control_the_orchestrator(
    live_server_url: str,
) -> None:
    # Arrange
    actions = ["status", "start", "pause", "stop"]

    # Act
    results = [
        run_cli("--url", live_server_url, "orchestrator", action)
        for action in actions
    ]

    # Assert
    assert [result.returncode for result in results] == [0, 0, 0, 0]
    assert [json.loads(result.stdout)["status"] for result in results] == [
        "running",
        "running",
        "paused",
        "stopped",
    ]
    assert all(result.stderr == "" for result in results)


def test_user_can_manage_processes(live_server_url: str) -> None:
    # Arrange
    create_arguments = [
        "--url",
        live_server_url,
        "process",
        "create",
        "--name",
        "Daily report",
        "--type",
        "python",
        "--inline",
        "print('ready')",
    ]

    # Act
    create_result = run_cli(*create_arguments)
    process = json.loads(create_result.stdout)
    process_id = process["process_id"]
    list_result = run_cli("--url", live_server_url, "process", "list")
    get_result = run_cli(
        "--url", live_server_url, "process", "get", process_id
    )
    update_result = run_cli(
        "--url",
        live_server_url,
        "process",
        "update",
        process_id,
        "--name",
        "Weekly report",
        "--type",
        "bash",
        "--file",
        "file_process.sh",
    )
    disable_result = run_cli(
        "--url", live_server_url, "process", "disable", process_id
    )
    enable_result = run_cli(
        "--url", live_server_url, "process", "enable", process_id
    )
    delete_result = run_cli(
        "--url", live_server_url, "process", "delete", process_id
    )

    # Assert
    results = [
        create_result,
        list_result,
        get_result,
        update_result,
        disable_result,
        enable_result,
        delete_result,
    ]
    assert [result.returncode for result in results] == [0] * 7
    assert json.loads(list_result.stdout) == [process]
    assert json.loads(get_result.stdout) == process
    updated_process = json.loads(update_result.stdout)
    assert updated_process["name"] == "Weekly report"
    assert updated_process["type"] == "bash"
    assert updated_process["source"] == {
        "kind": "file",
        "path": "file_process.sh",
    }
    assert json.loads(disable_result.stdout)["enabled"] is False
    assert json.loads(enable_result.stdout)["enabled"] is True
    assert delete_result.stdout == ""
    assert all(result.stderr == "" for result in results)


def test_user_can_create_a_job_with_process_arguments(
    live_server_url: str,
) -> None:
    # Arrange
    process_result = run_cli(
        "--url",
        live_server_url,
        "process",
        "create",
        "--name",
        "Contact agent",
        "--type",
        "python",
        "--inline",
        "print('contact agent')",
    )
    process_id = json.loads(process_result.stdout)["process_id"]

    # Act
    result = run_cli(
        "--url",
        live_server_url,
        "job",
        "create",
        "--process-id",
        process_id,
        "--",
        "--campaign-location",
        "Leeds, England",
    )

    # Assert
    assert result.returncode == 0, result.stderr
    assert json.loads(result.stdout)["arguments"] == [
        "--campaign-location",
        "Leeds, England",
    ]
    assert result.stderr == ""


def test_user_can_manage_jobs_and_read_run_history(
    live_server_url: str,
) -> None:
    # Arrange
    future_run = (datetime.now(UTC) + timedelta(hours=1)).isoformat()
    pause_result = run_cli(
        "--url", live_server_url, "orchestrator", "pause"
    )
    process_result = run_cli(
        "--url",
        live_server_url,
        "process",
        "create",
        "--name",
        "Run history process",
        "--type",
        "python",
        "--inline",
        "print('CLI run complete')",
    )
    process_id = json.loads(process_result.stdout)["process_id"]

    # Act
    create_result = run_cli(
        "--url",
        live_server_url,
        "job",
        "create",
        "--process-id",
        process_id,
        "--recurring",
        "--cron",
        "*/5 * * * *",
        "--next-run-at",
        future_run,
    )
    job = json.loads(create_result.stdout)
    job_id = job["job_id"]
    list_result = run_cli("--url", live_server_url, "job", "list")
    get_result = run_cli("--url", live_server_url, "job", "get", job_id)
    update_result = run_cli(
        "--url", live_server_url, "job", "update", job_id, "--inactive"
    )
    run_now_result = run_cli(
        "--url", live_server_url, "job", "run-now", job_id
    )
    start_result = run_cli(
        "--url", live_server_url, "orchestrator", "start"
    )

    deadline = monotonic() + 5
    runs = []
    run_list_result = None
    while monotonic() < deadline:
        run_list_result = run_cli(
            "--url",
            live_server_url,
            "run",
            "list",
            "--job-id",
            job_id,
            "--limit",
            "25",
        )
        runs = json.loads(run_list_result.stdout)
        if runs and runs[0]["status"] == "completed":
            break
        sleep(0.05)

    disposable_result = run_cli(
        "--url",
        live_server_url,
        "job",
        "create",
        "--process-id",
        process_id,
        "--next-run-at",
        future_run,
    )
    disposable_job_id = json.loads(disposable_result.stdout)["job_id"]
    delete_result = run_cli(
        "--url", live_server_url, "job", "delete", disposable_job_id
    )

    # Assert
    assert pause_result.returncode == 0, pause_result.stderr
    assert process_result.returncode == 0, process_result.stderr
    results = [
        create_result,
        list_result,
        get_result,
        update_result,
        run_now_result,
        start_result,
        run_list_result,
        disposable_result,
        delete_result,
    ]
    assert all(result is not None and result.returncode == 0 for result in results)
    assert json.loads(list_result.stdout) == [job]
    assert json.loads(get_result.stdout) == job
    assert json.loads(update_result.stdout)["active"] is False
    assert json.loads(run_now_result.stdout)["active"] is True
    assert json.loads(start_result.stdout) == {"status": "running"}
    assert runs and runs[0]["status"] == "completed"
    assert runs[0]["captured_output"] == "CLI run complete\n"
    assert delete_result.stdout == ""
    assert all(result is not None and result.stderr == "" for result in results)


def test_empty_updates_fail_before_calling_the_api() -> None:
    # Arrange
    unavailable_url = "http://127.0.0.1:0"
    identifier = "4ee6f8f6-0280-4f8e-a1bc-8d056ec8df10"

    # Act
    process_result = run_cli(
        "--url",
        unavailable_url,
        "process",
        "update",
        identifier,
    )
    job_result = run_cli(
        "--url",
        unavailable_url,
        "job",
        "update",
        identifier,
    )

    # Assert
    assert process_result.returncode == 2
    assert "process update requires at least one change" in process_result.stderr
    assert job_result.returncode == 2
    assert "job update requires at least one change" in job_result.stderr


def test_api_errors_are_json_on_stderr(live_server_url: str) -> None:
    # Arrange
    missing_process_id = "4ee6f8f6-0280-4f8e-a1bc-8d056ec8df10"

    # Act
    result = run_cli(
        "--url",
        live_server_url,
        "process",
        "get",
        missing_process_id,
    )

    # Assert
    assert result.returncode == 1
    assert result.stdout == ""
    assert json.loads(result.stderr) == {
        "error": {
            "type": "http",
            "status": 404,
            "detail": "process not found",
        }
    }


def test_invalid_server_url_is_a_usage_error() -> None:
    # Arrange
    invalid_url = "not-a-url"

    # Act
    result = run_cli("--url", invalid_url, "health")

    # Assert
    assert result.returncode == 2
    assert result.stdout == ""
    assert "must be an HTTP or HTTPS URL" in result.stderr
    assert "Traceback" not in result.stderr


def test_network_errors_are_json_on_stderr() -> None:
    # Arrange
    unavailable_url = "http://127.0.0.1:0"

    # Act
    result = run_cli("--url", unavailable_url, "health")

    # Assert
    assert result.returncode == 1
    assert result.stdout == ""
    error = json.loads(result.stderr)["error"]
    assert error["type"] == "network"
    assert error["detail"]

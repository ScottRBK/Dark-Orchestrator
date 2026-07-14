import json
import os
import subprocess
from pathlib import Path

from conftest import RecordedRequest, StubApi


REPOSITORY_ROOT = Path(__file__).parents[1]
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


def test_user_can_check_service_health(stub_api: StubApi) -> None:
    # Arrange
    health = {
        "service": "Dark Orchestrator",
        "status": "running",
        "database": "up",
    }
    stub_api.respond(health)

    # Act
    result = run_cli("--url", stub_api.url, "health")

    # Assert
    assert result.returncode == 0, result.stderr
    assert json.loads(result.stdout) == health
    assert result.stderr == ""
    assert stub_api.requests == [
        RecordedRequest(method="GET", path="/api/health"),
    ]


def test_user_can_select_the_server_with_an_environment_variable(
    stub_api: StubApi,
) -> None:
    # Arrange
    status = {"status": "running"}
    stub_api.respond(status)

    # Act
    result = run_cli(
        "orchestrator",
        "status",
        env={"DARK_ORCH_API_URL": stub_api.url},
    )

    # Assert
    assert result.returncode == 0, result.stderr
    assert json.loads(result.stdout) == status
    assert stub_api.requests == [
        RecordedRequest(method="GET", path="/api/orchestrator"),
    ]


def test_user_can_inspect_and_control_the_orchestrator(stub_api: StubApi) -> None:
    # Arrange
    expected_states = ["running", "running", "paused", "stopped"]
    for state in expected_states:
        stub_api.respond({"status": state})

    # Act
    results = [
        run_cli("--url", stub_api.url, "orchestrator", action)
        for action in ["status", "start", "pause", "stop"]
    ]

    # Assert
    assert [result.returncode for result in results] == [0, 0, 0, 0]
    states = [json.loads(result.stdout)["status"] for result in results]
    assert states == expected_states
    assert all(result.stderr == "" for result in results)
    assert stub_api.requests == [
        RecordedRequest(method="GET", path="/api/orchestrator"),
        RecordedRequest(method="POST", path="/api/orchestrator/start"),
        RecordedRequest(method="POST", path="/api/orchestrator/pause"),
        RecordedRequest(method="POST", path="/api/orchestrator/stop"),
    ]


def test_user_can_manage_processes(stub_api: StubApi) -> None:
    # Arrange
    process_id = "4ee6f8f6-0280-4f8e-a1bc-8d056ec8df10"
    process = {
        "process_id": process_id,
        "name": "Daily report",
        "type": "python",
        "source": {"kind": "inline", "content": "print('ready')"},
        "enabled": True,
    }
    updated_process = {
        **process,
        "name": "Weekly report",
        "type": "bash",
        "source": {"kind": "file", "path": "reports/weekly.sh"},
    }
    disabled_process = {**updated_process, "enabled": False}
    responses = [
        process,
        [process],
        process,
        updated_process,
        disabled_process,
        updated_process,
    ]
    for response in responses:
        stub_api.respond(response)
    stub_api.respond(status=204)

    # Act
    results = [
        run_cli(
            "--url",
            stub_api.url,
            "process",
            "create",
            "--name",
            "Daily report",
            "--type",
            "python",
            "--inline",
            "print('ready')",
        ),
        run_cli("--url", stub_api.url, "process", "list"),
        run_cli("--url", stub_api.url, "process", "get", process_id),
        run_cli(
            "--url",
            stub_api.url,
            "process",
            "update",
            process_id,
            "--name",
            "Weekly report",
            "--type",
            "bash",
            "--file",
            "reports/weekly.sh",
        ),
        run_cli("--url", stub_api.url, "process", "disable", process_id),
        run_cli("--url", stub_api.url, "process", "enable", process_id),
        run_cli("--url", stub_api.url, "process", "delete", process_id),
    ]

    # Assert
    assert [result.returncode for result in results] == [0] * 7
    assert [json.loads(result.stdout) for result in results[:6]] == responses
    assert results[6].stdout == ""
    assert all(result.stderr == "" for result in results)
    assert stub_api.requests == [
        RecordedRequest(
            method="POST",
            path="/api/processes",
            body={
                "name": "Daily report",
                "type": "python",
                "source": {"kind": "inline", "content": "print('ready')"},
            },
        ),
        RecordedRequest(method="GET", path="/api/processes"),
        RecordedRequest(method="GET", path=f"/api/processes/{process_id}"),
        RecordedRequest(
            method="PATCH",
            path=f"/api/processes/{process_id}",
            body={
                "name": "Weekly report",
                "type": "bash",
                "source": {"kind": "file", "path": "reports/weekly.sh"},
            },
        ),
        RecordedRequest(
            method="POST",
            path=f"/api/processes/{process_id}/disable",
        ),
        RecordedRequest(
            method="POST",
            path=f"/api/processes/{process_id}/enable",
        ),
        RecordedRequest(method="DELETE", path=f"/api/processes/{process_id}"),
    ]


def test_user_can_manage_jobs_and_read_run_history(stub_api: StubApi) -> None:
    # Arrange
    process_id = "4ee6f8f6-0280-4f8e-a1bc-8d056ec8df10"
    job_id = "f9e3d5e0-9457-4d28-820d-56e8bbd2dfba"
    next_run_at = "2026-07-15T09:30:00+00:00"
    job = {
        "job_id": job_id,
        "process": {"process_id": process_id},
        "recurring": True,
        "cron": "*/5 * * * *",
        "next_run_at": next_run_at,
        "active": True,
    }
    inactive_job = {**job, "active": False}
    runs = [
        {
            "job_run_id": "b4761fb0-7160-4668-a98f-0df958c92e7c",
            "job": job,
            "status": "completed",
            "captured_output": "ready\n",
        }
    ]
    responses = [job, [job], job, inactive_job, job, runs]
    for response in responses:
        stub_api.respond(response)
    stub_api.respond(status=204)

    # Act
    results = [
        run_cli(
            "--url",
            stub_api.url,
            "job",
            "create",
            "--process-id",
            process_id,
            "--recurring",
            "--cron",
            "*/5 * * * *",
            "--next-run-at",
            next_run_at,
        ),
        run_cli("--url", stub_api.url, "job", "list"),
        run_cli("--url", stub_api.url, "job", "get", job_id),
        run_cli(
            "--url",
            stub_api.url,
            "job",
            "update",
            job_id,
            "--inactive",
            "--next-run-at",
            next_run_at,
        ),
        run_cli("--url", stub_api.url, "job", "run-now", job_id),
        run_cli(
            "--url",
            stub_api.url,
            "run",
            "list",
            "--job-id",
            job_id,
            "--limit",
            "25",
        ),
        run_cli("--url", stub_api.url, "job", "delete", job_id),
    ]

    # Assert
    assert [result.returncode for result in results] == [0] * 7
    assert [json.loads(result.stdout) for result in results[:6]] == responses
    assert results[6].stdout == ""
    assert all(result.stderr == "" for result in results)
    assert stub_api.requests == [
        RecordedRequest(
            method="POST",
            path="/api/jobs",
            body={
                "process_id": process_id,
                "recurring": True,
                "cron": "*/5 * * * *",
                "next_run_at": next_run_at,
            },
        ),
        RecordedRequest(method="GET", path="/api/jobs"),
        RecordedRequest(method="GET", path=f"/api/jobs/{job_id}"),
        RecordedRequest(
            method="PATCH",
            path=f"/api/jobs/{job_id}",
            body={"active": False, "next_run_at": next_run_at},
        ),
        RecordedRequest(method="POST", path=f"/api/jobs/{job_id}/run-now"),
        RecordedRequest(
            method="GET",
            path=f"/api/runs?job_id={job_id}&limit=25",
        ),
        RecordedRequest(method="DELETE", path=f"/api/jobs/{job_id}"),
    ]


def test_empty_updates_fail_before_calling_the_api(stub_api: StubApi) -> None:
    # Arrange
    identifier = "4ee6f8f6-0280-4f8e-a1bc-8d056ec8df10"

    # Act
    process_result = run_cli(
        "--url",
        stub_api.url,
        "process",
        "update",
        identifier,
    )
    job_result = run_cli(
        "--url",
        stub_api.url,
        "job",
        "update",
        identifier,
    )

    # Assert
    assert process_result.returncode == 2
    assert "process update requires at least one change" in process_result.stderr
    assert job_result.returncode == 2
    assert "job update requires at least one change" in job_result.stderr
    assert stub_api.requests == []


def test_api_errors_are_json_on_stderr(stub_api: StubApi) -> None:
    # Arrange
    process_id = "4ee6f8f6-0280-4f8e-a1bc-8d056ec8df10"
    stub_api.respond({"detail": f"Process {process_id} was not found"}, status=404)

    # Act
    result = run_cli("--url", stub_api.url, "process", "get", process_id)

    # Assert
    assert result.returncode == 1
    assert result.stdout == ""
    assert json.loads(result.stderr) == {
        "error": {
            "type": "http",
            "status": 404,
            "detail": f"Process {process_id} was not found",
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


def test_invalid_server_responses_are_json_on_stderr(stub_api: StubApi) -> None:
    # Arrange
    stub_api.respond(b"not-json")

    # Act
    result = run_cli("--url", stub_api.url, "health")

    # Assert
    assert result.returncode == 1
    assert result.stdout == ""
    assert json.loads(result.stderr) == {
        "error": {
            "type": "response",
            "detail": "Server returned invalid JSON",
        }
    }

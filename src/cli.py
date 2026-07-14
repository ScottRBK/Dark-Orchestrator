import argparse
import json
import os
import sys
from typing import Any
from urllib.error import HTTPError, URLError
from urllib.parse import quote, urlencode, urlparse
from urllib.request import Request, urlopen


DEFAULT_API_URL = "http://127.0.0.1:8099"


class ApiClient:
    def __init__(self, base_url: str) -> None:
        self._base_url = base_url.rstrip("/")

    def request(
        self,
        method: str,
        path: str,
        body: dict[str, Any] | None = None,
    ) -> Any:
        encoded_body = None if body is None else json.dumps(body).encode()
        headers = {"Content-Type": "application/json"} if encoded_body else {}
        request = Request(
            f"{self._base_url}{path}",
            data=encoded_body,
            headers=headers,
            method=method,
        )
        with urlopen(request, timeout=10) as response:
            content = response.read()
            return json.loads(content) if content else None


def parse_api_url(value: str) -> str:
    parsed = urlparse(value)
    if parsed.scheme not in {"http", "https"} or not parsed.netloc:
        raise argparse.ArgumentTypeError("must be an HTTP or HTTPS URL")
    return value


def add_source_arguments(
    parser: argparse.ArgumentParser,
    *,
    required: bool,
) -> None:
    source = parser.add_mutually_exclusive_group(required=required)
    source.add_argument(
        "--inline",
        dest="inline_content",
        help="Inline script content",
    )
    source.add_argument(
        "--file",
        dest="file_path",
        help="Script path relative to the server's script root",
    )


def add_process_commands(subcommands: Any) -> None:
    process = subcommands.add_parser("process", help="Manage processes")
    commands = process.add_subparsers(dest="process_command", required=True)

    commands.add_parser("list", help="List processes")

    get_process = commands.add_parser("get", help="Get a process")
    get_process.add_argument("process_id")

    create_process = commands.add_parser("create", help="Create a process")
    create_process.add_argument("--name", required=True)
    create_process.add_argument("--type", required=True, choices=["bash", "python"])
    add_source_arguments(create_process, required=True)

    update_process = commands.add_parser("update", help="Update a process")
    update_process.add_argument("process_id")
    update_process.add_argument("--name")
    update_process.add_argument("--type", choices=["bash", "python"])
    add_source_arguments(update_process, required=False)

    for action in ["enable", "disable", "delete"]:
        command = commands.add_parser(action, help=f"{action.title()} a process")
        command.add_argument("process_id")


def add_job_commands(subcommands: Any) -> None:
    job = subcommands.add_parser("job", help="Manage jobs")
    commands = job.add_subparsers(dest="job_command", required=True)

    commands.add_parser("list", help="List jobs")

    get_job = commands.add_parser("get", help="Get a job")
    get_job.add_argument("job_id")

    create_job = commands.add_parser("create", help="Create a job")
    create_job.add_argument("--process-id", required=True)
    create_job.add_argument("--recurring", action="store_true")
    create_job.add_argument("--cron")
    create_job.add_argument("--next-run-at")

    update_job = commands.add_parser("update", help="Update a job")
    update_job.add_argument("job_id")
    active = update_job.add_mutually_exclusive_group()
    active.add_argument("--active", dest="active", action="store_true", default=None)
    active.add_argument("--inactive", dest="active", action="store_false", default=None)
    update_job.add_argument("--next-run-at")

    run_job = commands.add_parser("run-now", help="Queue a job to run now")
    run_job.add_argument("job_id")

    delete_job = commands.add_parser("delete", help="Delete a job")
    delete_job.add_argument("job_id")


def add_run_commands(subcommands: Any) -> None:
    run = subcommands.add_parser("run", help="Read run history")
    commands = run.add_subparsers(dest="run_command", required=True)
    list_runs = commands.add_parser("list", help="List runs")
    list_runs.add_argument("--job-id")
    list_runs.add_argument("--limit", type=int, default=100)


def create_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        prog="dark-orchestrator",
        description="Command-line client for Dark Orchestrator",
    )
    parser.add_argument(
        "--url",
        type=parse_api_url,
        default=os.environ.get("DARK_ORCH_API_URL", DEFAULT_API_URL),
        help="Dark Orchestrator server URL",
    )
    subcommands = parser.add_subparsers(dest="command", required=True)
    health = subcommands.add_parser("health", help="Show service health")
    health.set_defaults(api_method="GET", api_path="/api/health")

    orchestrator = subcommands.add_parser(
        "orchestrator",
        help="Inspect or control the orchestrator",
    )
    orchestrator_commands = orchestrator.add_subparsers(
        dest="orchestrator_command",
        required=True,
    )
    orchestrator_actions = {
        "status": ("GET", "/api/orchestrator"),
        "start": ("POST", "/api/orchestrator/start"),
        "pause": ("POST", "/api/orchestrator/pause"),
        "stop": ("POST", "/api/orchestrator/stop"),
    }
    for name, (method, path) in orchestrator_actions.items():
        command = orchestrator_commands.add_parser(name)
        command.set_defaults(api_method=method, api_path=path)

    add_process_commands(subcommands)
    add_job_commands(subcommands)
    add_run_commands(subcommands)
    return parser


def process_request(
    arguments: argparse.Namespace,
    parser: argparse.ArgumentParser,
) -> tuple[str, str, dict[str, Any] | None]:
    command = arguments.process_command
    process_id = quote(getattr(arguments, "process_id", ""), safe="")

    if command == "list":
        return "GET", "/api/processes", None
    if command == "get":
        return "GET", f"/api/processes/{process_id}", None
    if command == "create":
        source = process_source(arguments)
        return (
            "POST",
            "/api/processes",
            {"name": arguments.name, "type": arguments.type, "source": source},
        )
    if command == "update":
        body = {
            name: value
            for name in ["name", "type"]
            if (value := getattr(arguments, name)) is not None
        }
        source = process_source(arguments)
        if source is not None:
            body["source"] = source
        if not body:
            parser.error("process update requires at least one change")
        return "PATCH", f"/api/processes/{process_id}", body
    if command in {"enable", "disable"}:
        return "POST", f"/api/processes/{process_id}/{command}", None
    return "DELETE", f"/api/processes/{process_id}", None


def process_source(arguments: argparse.Namespace) -> dict[str, str] | None:
    if arguments.inline_content is not None:
        return {"kind": "inline", "content": arguments.inline_content}
    if arguments.file_path is not None:
        return {"kind": "file", "path": arguments.file_path}
    return None


def job_request(
    arguments: argparse.Namespace,
    parser: argparse.ArgumentParser,
) -> tuple[str, str, dict[str, Any] | None]:
    command = arguments.job_command
    job_id = quote(getattr(arguments, "job_id", ""), safe="")

    if command == "list":
        return "GET", "/api/jobs", None
    if command == "get":
        return "GET", f"/api/jobs/{job_id}", None
    if command == "create":
        body: dict[str, Any] = {
            "process_id": arguments.process_id,
            "recurring": arguments.recurring,
        }
        for name in ["cron", "next_run_at"]:
            if (value := getattr(arguments, name)) is not None:
                body[name] = value
        return "POST", "/api/jobs", body
    if command == "update":
        body = {
            name: value
            for name in ["active", "next_run_at"]
            if (value := getattr(arguments, name)) is not None
        }
        if not body:
            parser.error("job update requires at least one change")
        return "PATCH", f"/api/jobs/{job_id}", body
    if command == "run-now":
        return "POST", f"/api/jobs/{job_id}/run-now", None
    return "DELETE", f"/api/jobs/{job_id}", None


def run_request(
    arguments: argparse.Namespace,
) -> tuple[str, str, dict[str, Any] | None]:
    query = {"limit": arguments.limit}
    if arguments.job_id is not None:
        query = {"job_id": arguments.job_id, **query}
    return "GET", f"/api/runs?{urlencode(query)}", None


def request_details(
    arguments: argparse.Namespace,
    parser: argparse.ArgumentParser,
) -> tuple[str, str, dict[str, Any] | None]:
    if arguments.command == "process":
        return process_request(arguments, parser)
    if arguments.command == "job":
        return job_request(arguments, parser)
    if arguments.command == "run":
        return run_request(arguments)
    return arguments.api_method, arguments.api_path, None


def http_error_detail(error: HTTPError) -> Any:
    content = error.read()
    if not content:
        return error.reason
    try:
        response = json.loads(content)
    except json.JSONDecodeError:
        return content.decode(errors="replace")
    if isinstance(response, dict) and "detail" in response:
        return response["detail"]
    return response


def write_error(
    error_type: str,
    detail: Any,
    *,
    status: int | None = None,
) -> None:
    error: dict[str, Any] = {"type": error_type}
    if status is not None:
        error["status"] = status
    error["detail"] = detail
    print(json.dumps({"error": error}, indent=2), file=sys.stderr)


def main() -> int:
    parser = create_parser()
    arguments = parser.parse_args()
    method, path, body = request_details(arguments, parser)
    try:
        result = ApiClient(arguments.url).request(method, path, body)
    except HTTPError as error:
        write_error(
            "http",
            http_error_detail(error),
            status=error.code,
        )
        return 1
    except URLError as error:
        write_error("network", str(error.reason))
        return 1
    except json.JSONDecodeError:
        write_error("response", "Server returned invalid JSON")
        return 1
    if result is not None:
        print(json.dumps(result, indent=2))
    return 0

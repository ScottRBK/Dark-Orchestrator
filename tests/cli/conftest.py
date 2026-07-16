import os
import socket
import subprocess
import sys
from collections.abc import Iterator
from pathlib import Path
from time import monotonic, sleep
from urllib.error import URLError
from urllib.request import urlopen

import pytest


REPOSITORY_ROOT = Path(__file__).parents[2]
TEST_DATABASE_URL = (
    "postgresql://dark_orchestrator:dark_orchestrator@"
    "localhost:54329/dark_orchestrator_test"
)


def available_port() -> int:
    with socket.socket() as server_socket:
        server_socket.bind(("127.0.0.1", 0))
        return server_socket.getsockname()[1]


@pytest.fixture
def live_server_url(clean_database: None) -> Iterator[str]:
    host = "127.0.0.1"
    port = available_port()
    url = f"http://{host}:{port}"
    environment = {
        **os.environ,
        "DARK_ORCH_DATABASE_URL": TEST_DATABASE_URL,
        "DARK_ORCH_HEART_BEAT_INTERVAL": "0.05",
        "DARK_ORCH_SCRIPT_ROOT": str(REPOSITORY_ROOT / "tests" / "cli" / "fixtures"),
    }
    server = subprocess.Popen(
        [
            sys.executable,
            "-m",
            "uvicorn",
            "main:app",
            "--host",
            host,
            "--port",
            str(port),
            "--log-level",
            "warning",
        ],
        cwd=REPOSITORY_ROOT,
        env=environment,
        stdout=subprocess.PIPE,
        stderr=subprocess.STDOUT,
        text=True,
    )

    try:
        deadline = monotonic() + 10
        while monotonic() < deadline:
            if server.poll() is not None:
                output = server.stdout.read() if server.stdout else ""
                raise RuntimeError(f"CLI test server failed to start:\n{output}")
            try:
                with urlopen(f"{url}/api/health", timeout=0.2):
                    break
            except URLError:
                sleep(0.05)
        else:
            raise RuntimeError("CLI test server did not become ready")

        yield url
    finally:
        server.terminate()
        try:
            server.wait(timeout=5)
        except subprocess.TimeoutExpired:
            server.kill()
            server.wait(timeout=5)

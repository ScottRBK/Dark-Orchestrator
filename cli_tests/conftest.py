from collections import deque
from dataclasses import dataclass
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from threading import Thread
from typing import Any

import pytest


@dataclass(frozen=True)
class RecordedRequest:
    method: str
    path: str
    body: Any = None


@dataclass(frozen=True)
class StubResponse:
    status: int
    body: Any = None


class StubApi:
    def __init__(self) -> None:
        self.requests: list[RecordedRequest] = []
        self.responses: deque[StubResponse] = deque()
        self.url = ""

    def respond(self, body: Any = None, status: int = 200) -> None:
        self.responses.append(StubResponse(status=status, body=body))


class StubRequestHandler(BaseHTTPRequestHandler):
    server: "StubApiServer"

    def do_GET(self) -> None:
        self._handle_request()

    def do_POST(self) -> None:
        self._handle_request()

    def do_PATCH(self) -> None:
        self._handle_request()

    def do_DELETE(self) -> None:
        self._handle_request()

    def log_message(self, format: str, *args: object) -> None:
        pass

    def _handle_request(self) -> None:
        import json

        content_length = int(self.headers.get("Content-Length", "0"))
        content = self.rfile.read(content_length) if content_length else b""
        body = json.loads(content) if content else None
        self.server.stub.requests.append(
            RecordedRequest(method=self.command, path=self.path, body=body)
        )

        if self.server.stub.responses:
            response = self.server.stub.responses.popleft()
        else:
            response = StubResponse(
                status=500,
                body={"detail": "The test did not configure a response"},
            )

        if isinstance(response.body, bytes):
            encoded_body = response.body
            content_type = "text/plain"
        else:
            encoded_body = b"" if response.body is None else json.dumps(response.body).encode()
            content_type = "application/json"
        self.send_response(response.status)
        if encoded_body:
            self.send_header("Content-Type", content_type)
        self.send_header("Content-Length", str(len(encoded_body)))
        self.end_headers()
        self.wfile.write(encoded_body)


class StubApiServer(ThreadingHTTPServer):
    def __init__(self, stub: StubApi) -> None:
        super().__init__(("127.0.0.1", 0), StubRequestHandler)
        self.stub = stub


@pytest.fixture
def stub_api() -> StubApi:
    stub = StubApi()
    server = StubApiServer(stub)
    host, port = server.server_address
    stub.url = f"http://{host}:{port}"
    thread = Thread(target=server.serve_forever, daemon=True)
    thread.start()

    yield stub

    server.shutdown()
    server.server_close()
    thread.join()

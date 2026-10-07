"""A real loopback HTTP server that speaks laya-serve's /v1/systemone shape."""

from __future__ import annotations

import json
import threading
import time
from collections.abc import Iterator
from contextlib import contextmanager
from dataclasses import dataclass, field
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from typing import Any


@dataclass
class FakeLayaBehaviour:
    """What the fake server returns; mutable while the server is running."""

    choice: str = "general"
    confidence: float = 0.9
    status_code: int = 200
    delay_seconds: float = 0.0
    raw_body: bytes | None = None
    requests: list[dict[str, Any]] = field(default_factory=list)

    def body(self) -> bytes:
        if self.raw_body is not None:
            return self.raw_body
        return json.dumps(
            {
                "model": "fake-laya",
                "answers": {
                    "intent": {
                        "type": "choice",
                        "choice": self.choice,
                        "confidence": self.confidence,
                    }
                },
                "routing": {"reason": "fake"},
            }
        ).encode()


@contextmanager
def fake_laya_server() -> Iterator[tuple[str, FakeLayaBehaviour]]:
    behaviour = FakeLayaBehaviour()

    class Handler(BaseHTTPRequestHandler):
        def do_POST(self) -> None:  # noqa: N802 - http.server API
            length = int(self.headers.get("Content-Length", "0"))
            behaviour.requests.append(
                {
                    "path": self.path,
                    "authorization": self.headers.get("Authorization"),
                    "body": json.loads(self.rfile.read(length)),
                }
            )
            if behaviour.delay_seconds:
                time.sleep(behaviour.delay_seconds)
            body = behaviour.body()
            try:
                self.send_response(behaviour.status_code)
                self.send_header("Content-Type", "application/json")
                self.send_header("Content-Length", str(len(body)))
                self.end_headers()
                self.wfile.write(body)
            except (BrokenPipeError, ConnectionResetError, ConnectionAbortedError):
                pass  # client gave up (timeout test)

        def log_message(self, *_: Any) -> None:
            return None

    server = ThreadingHTTPServer(("127.0.0.1", 0), Handler)
    server.daemon_threads = True
    thread = threading.Thread(target=server.serve_forever, daemon=True)
    thread.start()
    try:
        host, port = server.server_address[:2]
        yield f"http://{host}:{port}/v1/systemone", behaviour
    finally:
        server.shutdown()
        server.server_close()

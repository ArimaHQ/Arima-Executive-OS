"""Authenticated local SMTP sink for the verification scripts.

Accepts AUTH LOGIN/PLAIN from user ``arima-audit`` (any password) on
127.0.0.1:1025 without TLS and writes each message to
``<mail-dir>/<ns>_<recipient>.eml``. Local verification only; requires the
dev-only ``aiosmtpd`` package. Point the API at it with EMAIL_PROVIDER=smtp,
SMTP_HOST=127.0.0.1, SMTP_PORT=1025, SMTP_USE_TLS=false,
SMTP_USERNAME=arima-audit, SMTP_PASSWORD=<anything>.
"""

import sys
import time
from pathlib import Path

from aiosmtpd.controller import Controller
from aiosmtpd.smtp import AuthResult, LoginPassword


class Handler:
    def __init__(self, directory: Path) -> None:
        self.directory = directory

    async def handle_DATA(self, server, session, envelope):
        target = self.directory / f"{time.time_ns()}_{envelope.rcpt_tos[0]}.eml"
        target.write_bytes(envelope.content)
        return "250 OK"


def authenticator(server, session, envelope, mechanism, auth_data) -> AuthResult:
    return AuthResult(
        success=isinstance(auth_data, LoginPassword) and auth_data.login == b"arima-audit"
    )


def main() -> None:
    directory = Path(sys.argv[1])
    directory.mkdir(parents=True, exist_ok=True)
    controller = Controller(
        Handler(directory), hostname="127.0.0.1", port=1025,
        authenticator=authenticator, auth_require_tls=False,
    )
    controller.start()
    try:
        while True:
            time.sleep(3600)
    finally:
        controller.stop()


if __name__ == "__main__":
    main()

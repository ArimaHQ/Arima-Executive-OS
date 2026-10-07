import sqlite3

from sqlalchemy import event
from sqlalchemy.engine import Engine

from tests.auth.conftest import auth_context
from tests.management.conftest import management_context

__all__ = ("auth_context", "management_context")


@event.listens_for(Engine, "connect")
def _fast_test_sqlite(dbapi_connection, _record) -> None:
    # Throwaway test databases don't need durable journals. On Windows, the
    # per-statement journal file is rescanned by antivirus and schema creation
    # alone takes ~90s per test without this.
    is_sqlite = isinstance(dbapi_connection, sqlite3.Connection) or type(
        dbapi_connection
    ).__module__.startswith("sqlalchemy.dialects.sqlite")
    if not is_sqlite:
        return
    cursor = dbapi_connection.cursor()
    cursor.execute("PRAGMA journal_mode=MEMORY")
    cursor.execute("PRAGMA synchronous=OFF")
    cursor.close()

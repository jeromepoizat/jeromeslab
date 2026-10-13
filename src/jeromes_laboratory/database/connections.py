"""Short, deterministically closed SQLite contexts with coordinated local access."""

from __future__ import annotations

import sqlite3
import threading
from pathlib import Path
from types import TracebackType
from typing import Literal, Self

_locks: dict[str, threading.RLock] = {}
_locks_guard = threading.Lock()


class ManagedConnection(sqlite3.Connection):
    """Serialize local contexts, not network requests; release handles on every exit."""

    lock: threading.RLock

    def __enter__(self) -> Self:
        self.lock.acquire()
        try:
            super().__enter__()
        except BaseException:
            self.lock.release()
            raise
        return self

    def __exit__(
        self, kind: type[BaseException] | None, value: BaseException | None,
        traceback: TracebackType | None,
    ) -> Literal[False]:
        try:
            super().__exit__(kind, value, traceback)
            return False
        finally:
            try:
                self.close()
            finally:
                self.lock.release()


def connect_database(path: Path, *, timeout: float = 5) -> ManagedConnection:
    key = str(path.resolve()).casefold()
    with _locks_guard:
        lock = _locks.setdefault(key, threading.RLock())
    connection = sqlite3.connect(path, timeout=timeout, factory=ManagedConnection)
    connection.lock = lock
    connection.row_factory = sqlite3.Row
    return connection

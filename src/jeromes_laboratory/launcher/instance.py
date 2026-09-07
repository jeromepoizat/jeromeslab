"""Coordinate one running local application instance per user account."""

from __future__ import annotations

import json
import os
from collections.abc import Callable
from dataclasses import dataclass
from pathlib import Path
from uuid import uuid4

from platformdirs import user_config_path

from jeromes_laboratory.storage.workspace import APPLICATION_NAME


@dataclass(frozen=True)
class RunningInstance:
    """The small, temporary record published by the primary launcher."""

    instance_id: str
    port: int
    pid: int


@dataclass(frozen=True)
class InstanceClaim:
    """The claimed instance, and whether this launcher owns it."""

    instance: RunningInstance
    owns_instance: bool


class InstanceCoordinator:
    """Use an exclusive local record, recovering stale records safely."""

    def __init__(
        self,
        record_path: Path | None = None,
        *,
        health_checker: Callable[[RunningInstance], bool],
        process_is_running: Callable[[int], bool] | None = None,
    ) -> None:
        self.record_path = record_path or (
            user_config_path(appname=APPLICATION_NAME, appauthor=False) / "running-instance.json"
        )
        self._health_checker = health_checker
        self._process_is_running = process_is_running or self._default_process_is_running

    def claim(self, port: int) -> InstanceClaim:
        """Claim the record or return the healthy/alive primary instance."""
        candidate = RunningInstance(instance_id=uuid4().hex, port=port, pid=os.getpid())
        self.record_path.parent.mkdir(parents=True, exist_ok=True)
        while True:
            try:
                descriptor = os.open(
                    self.record_path,
                    os.O_CREAT | os.O_EXCL | os.O_WRONLY,
                )
            except FileExistsError:
                existing = self._read_record()
                if existing is not None and (
                    self._health_checker(existing) or self._process_is_running(existing.pid)
                ):
                    return InstanceClaim(instance=existing, owns_instance=False)
                self._remove_stale_record()
                continue
            try:
                with os.fdopen(descriptor, "w", encoding="utf-8") as record_file:
                    json.dump(candidate.__dict__, record_file, sort_keys=True)
                    record_file.flush()
                    os.fsync(record_file.fileno())
            except BaseException:
                self.record_path.unlink(missing_ok=True)
                raise
            return InstanceClaim(instance=candidate, owns_instance=True)

    def release(self, instance_id: str) -> None:
        """Remove only the record owned by this exact launcher."""
        existing = self._read_record()
        if existing is not None and existing.instance_id == instance_id:
            self.record_path.unlink(missing_ok=True)

    def _read_record(self) -> RunningInstance | None:
        try:
            content = json.loads(self.record_path.read_text(encoding="utf-8"))
            instance_id = content["instance_id"]
            port = content["port"]
            pid = content["pid"]
        except (OSError, TypeError, ValueError, KeyError, json.JSONDecodeError):
            return None
        if not isinstance(instance_id, str) or not isinstance(port, int) or not isinstance(pid, int):
            return None
        return RunningInstance(instance_id=instance_id, port=port, pid=pid)

    def _remove_stale_record(self) -> None:
        self.record_path.unlink(missing_ok=True)

    @staticmethod
    def _default_process_is_running(pid: int) -> bool:
        if pid <= 0:
            return False
        try:
            os.kill(pid, 0)
        except ProcessLookupError:
            return False
        except PermissionError:
            return True
        return True

"""Tests for the single local application instance coordinator."""

from pathlib import Path

import pytest

from jeromes_laboratory.launcher.instance import InstanceCoordinator


def test_first_launcher_claims_the_instance_record(tmp_path: Path) -> None:
    coordinator = InstanceCoordinator(
        tmp_path / "running-instance.json",
        health_checker=lambda _: False,
        process_is_running=lambda _: False,
    )

    claim = coordinator.claim(8123)

    assert claim.owns_instance is True
    assert claim.instance.port == 8123
    coordinator.release(claim.instance.instance_id)
    assert not coordinator.record_path.exists()


def test_second_launcher_uses_a_healthy_existing_instance(tmp_path: Path) -> None:
    record_path = tmp_path / "running-instance.json"
    first = InstanceCoordinator(
        record_path, health_checker=lambda _: False, process_is_running=lambda _: False
    ).claim(8123)
    second = InstanceCoordinator(
        record_path, health_checker=lambda _: True, process_is_running=lambda _: False
    ).claim(9123)

    assert second.owns_instance is False
    assert second.instance == first.instance


def test_stale_instance_record_is_replaced(tmp_path: Path) -> None:
    record_path = tmp_path / "running-instance.json"
    first = InstanceCoordinator(
        record_path, health_checker=lambda _: False, process_is_running=lambda _: False
    ).claim(8123)
    second = InstanceCoordinator(
        record_path, health_checker=lambda _: False, process_is_running=lambda _: False
    ).claim(9123)

    assert second.owns_instance is True
    assert second.instance.instance_id != first.instance.instance_id
    assert second.instance.port == 9123


def test_windows_pid_probe_error_is_treated_as_not_running(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    def raise_windows_probe_error(_: int, __: int) -> None:
        raise OSError(11, "incorrect format")

    monkeypatch.setattr("jeromes_laboratory.launcher.instance.os.kill", raise_windows_probe_error)

    assert InstanceCoordinator._default_process_is_running(1234) is False

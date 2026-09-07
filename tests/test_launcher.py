"""Tests for local launcher primitives."""

import socket

import pytest

from jeromes_laboratory.launcher.main import HOST, find_available_port, get_launch_port


def test_find_available_port_returns_bindable_loopback_port() -> None:
    port = find_available_port()

    with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as listener:
        listener.bind((HOST, port))


def test_get_launch_port_accepts_test_override(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("JEROMES_LABORATORY_PORT", "8765")

    assert get_launch_port() == 8765


def test_get_launch_port_rejects_invalid_override(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("JEROMES_LABORATORY_PORT", "70000")

    with pytest.raises(ValueError, match="between 1 and 65535"):
        get_launch_port()

"""Consistency checks for the dependency-free bootstrap metadata."""

from __future__ import annotations

import re
from pathlib import Path

REPOSITORY_ROOT = Path(__file__).resolve().parents[1]


def read_runtime_versions() -> dict[str, str]:
    values: dict[str, str] = {}
    metadata_path = REPOSITORY_ROOT / "bootstrap" / "runtime-versions.env"
    for line in metadata_path.read_text(encoding="utf-8").splitlines():
        stripped = line.strip()
        if stripped and not stripped.startswith("#"):
            key, value = stripped.split("=", maxsplit=1)
            values[key] = value
    return values


def test_bootstrap_versions_match_project_pins() -> None:
    versions = read_runtime_versions()
    python_pin = (REPOSITORY_ROOT / ".python-version").read_text(encoding="utf-8").strip()
    package_json = (REPOSITORY_ROOT / "frontend" / "package.json").read_text(encoding="utf-8")

    assert versions["PYTHON_VERSION"] == python_pin
    assert f'"packageManager": "pnpm@{versions["PNPM_VERSION"]}"' in package_json


def test_bootstrap_archive_checksums_are_sha256() -> None:
    versions = read_runtime_versions()
    checksum_values = [value for key, value in versions.items() if key.endswith("_SHA256")]

    assert len(checksum_values) == 12
    assert all(re.fullmatch(r"[0-9a-f]{64}", value) for value in checksum_values)

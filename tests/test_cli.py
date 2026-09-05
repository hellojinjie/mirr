from __future__ import annotations

import subprocess
import sys


def run_module(*args: str) -> subprocess.CompletedProcess[str]:
    return subprocess.run(
        [sys.executable, "-m", "mirr.cli", *args],
        check=False,
        capture_output=True,
        text=True,
    )


def test_help_exposes_nrm_shaped_commands() -> None:
    result = run_module("--help")

    assert result.returncode == 0
    for command in ("ls", "current", "use", "add", "del", "rename", "home", "test"):
        assert command in result.stdout


def test_version_uses_project_version() -> None:
    result = run_module("--version")

    assert result.returncode == 0
    assert result.stdout.strip() == "mirr, version 0.2.0"

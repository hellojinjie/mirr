from __future__ import annotations

import threading
from pathlib import Path
from typing import Optional
from urllib.error import URLError

import pytest
from click.testing import CliRunner
from conftest import IsolatedEnvironment

from uim.browser import BrowserError, open_index_home
from uim.catalog import Index
from uim.cli import cli
from uim.probe import ProbeResult, probe_index, probe_indexes


class FakeResponse:
    status = 200

    def __enter__(self):
        return self

    def __exit__(self, exc_type, exc_value, traceback):
        return None


def test_default_browser_opens_configured_homepage() -> None:
    opened: list[str] = []
    index = Index("company", "https://packages.example/simple", "https://packages.example")

    open_index_home(index, default_open=lambda url: opened.append(url) or True)

    assert opened == ["https://packages.example"]


def test_requested_browser_launches_argv_without_a_shell(tmp_path: Path) -> None:
    executable = tmp_path / "browser"
    executable.touch()
    launched: list[list[str]] = []
    index = Index("company", "https://packages.example/simple", "https://packages.example")

    open_index_home(
        index,
        browser="browser",
        which=lambda name: str(executable) if name == "browser" else None,
        launch=lambda argv: launched.append(list(argv)),
    )

    assert launched == [[str(executable), "https://packages.example"]]


def test_homepage_errors_are_actionable() -> None:
    with pytest.raises(BrowserError, match="no homepage"):
        open_index_home(Index("company", "https://packages.example/simple"))

    with pytest.raises(BrowserError, match="cannot find browser"):
        open_index_home(
            Index("company", "https://packages.example/simple", "https://packages.example"),
            browser="missing",
            which=lambda name: None,
        )

    with pytest.raises(BrowserError, match="could not open"):
        open_index_home(
            Index("company", "https://packages.example/simple", "https://packages.example"),
            default_open=lambda url: False,
        )


def test_probe_reports_success_status_and_elapsed_milliseconds() -> None:
    ticks = iter([10.0, 10.125])

    result = probe_index(
        Index("pypi", "https://pypi.org/simple"),
        opener=lambda request, timeout: FakeResponse(),
        clock=lambda: next(ticks),
    )

    assert result == ProbeResult(
        name="pypi",
        url="https://pypi.org/simple",
        ok=True,
        latency_ms=125.0,
        error=None,
    )


def test_probe_failure_redacts_url_credentials() -> None:
    def fail(request, timeout):
        raise URLError("https://alice:super-secret@packages.example/simple timed out")

    result = probe_index(
        Index("company", "https://alice:super-secret@packages.example/simple"),
        opener=fail,
    )

    assert not result.ok
    assert result.latency_ms is None
    assert "alice" not in (result.error or "")
    assert "super-secret" not in (result.error or "")


def test_probe_all_runs_concurrently_but_returns_catalog_order() -> None:
    barrier = threading.Barrier(2, timeout=2)
    indexes = [
        Index("first", "https://first.example/simple"),
        Index("second", "https://second.example/simple"),
    ]

    def synchronized_probe(index: Index, timeout: float) -> ProbeResult:
        barrier.wait()
        return ProbeResult(index.name, index.url, True, 1.0, None)

    results = probe_indexes(indexes, max_workers=2, probe=synchronized_probe)

    assert [result.name for result in results] == ["first", "second"]


def test_home_command_uses_catalog_homepage(
    isolated_env: IsolatedEnvironment,
    monkeypatch,
) -> None:
    opened: list[str] = []

    def record(index: Index, browser: Optional[str] = None) -> None:
        opened.append(f"{index.name}:{browser or 'default'}")

    monkeypatch.setattr("uim.cli.open_index_home", record)

    result = CliRunner().invoke(cli, ["home", "pypi"])

    assert result.exit_code == 0, result.output
    assert opened == ["pypi:default"]


def test_test_command_reports_one_or_all_without_mutating_config(
    isolated_env: IsolatedEnvironment,
    monkeypatch,
) -> None:
    user_config = isolated_env.xdg_config / "uv" / "uv.toml"
    user_config.parent.mkdir(parents=True)
    user_config.write_text('default-index = "https://pypi.org/simple"\n', encoding="utf-8")
    original = user_config.read_bytes()

    def successful(indexes, **kwargs):
        return [ProbeResult(index.name, index.url, True, 12.5, None) for index in indexes]

    monkeypatch.setattr("uim.cli.probe_indexes", successful)
    runner = CliRunner()

    one = runner.invoke(cli, ["test", "pypi"])
    all_indexes = runner.invoke(cli, ["test"])

    assert one.exit_code == 0, one.output
    assert one.output == "* pypi ---- 12 ms\n"
    assert all_indexes.exit_code == 0, all_indexes.output
    assert [line.lstrip("* ").split()[0] for line in all_indexes.output.splitlines()] == [
        "pypi",
        "tsinghua",
        "aliyun",
        "tencent",
        "huawei",
        "ustc",
    ]
    assert user_config.read_bytes() == original


def test_test_command_reports_endpoint_failure(
    isolated_env: IsolatedEnvironment,
    monkeypatch,
) -> None:
    def failed(indexes, **kwargs):
        index = indexes[0]
        return [ProbeResult(index.name, index.url, False, None, "TLS failure")]

    monkeypatch.setattr("uim.cli.probe_indexes", failed)

    result = CliRunner().invoke(cli, ["test", "pypi"])

    assert result.exit_code != 0
    assert "TLS failure" in result.output

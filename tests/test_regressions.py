from __future__ import annotations

import os
import shutil
import ssl
import subprocess
import tempfile
from pathlib import Path
from urllib.error import HTTPError, URLError

import pytest
from click.testing import CliRunner
from conftest import IsolatedEnvironment

from mirr.backends.uv import ConfigEditorError, LocalTarget, set_default_index
from mirr.browser import BrowserError, open_index_home
from mirr.catalog import CatalogError, CatalogStore, Index, default_catalog_path
from mirr.cli import cli
from mirr.probe import probe_index


class RedirectResponse:
    status = 302

    def __enter__(self):
        return self

    def __exit__(self, exc_type, exc_value, traceback):
        return None


def test_catalog_rejects_invalid_port_without_writing(tmp_path: Path) -> None:
    path = tmp_path / "config.toml"

    with pytest.raises(CatalogError, match="port"):
        CatalogStore(path).add("company", "https://packages.example.com:not-a-port/simple")

    assert not path.exists()


def test_default_catalog_path_honors_isolated_xdg_home(
    isolated_env: IsolatedEnvironment,
) -> None:
    assert default_catalog_path() == isolated_env.catalog_path


def test_delete_protects_user_selection_even_when_project_overrides_it(
    isolated_env: IsolatedEnvironment,
) -> None:
    runner = CliRunner()
    assert (
        runner.invoke(cli, ["add", "company", "https://packages.example.com/simple"]).exit_code == 0
    )
    assert runner.invoke(cli, ["use", "company"]).exit_code == 0
    (isolated_env.project / "uv.toml").write_text(
        'index-url = "https://pypi.org/simple"\n', encoding="utf-8"
    )

    result = runner.invoke(cli, ["del", "company"])

    assert result.exit_code != 0
    assert "currently selected" in result.output


def test_delete_without_name_requires_tty_and_prompts_when_interactive(
    isolated_env: IsolatedEnvironment,
    monkeypatch,
) -> None:
    runner = CliRunner()
    assert (
        runner.invoke(cli, ["add", "company", "https://packages.example.com/simple"]).exit_code == 0
    )

    noninteractive = runner.invoke(cli, ["del"])
    assert noninteractive.exit_code != 0
    assert "index name is required" in noninteractive.output

    monkeypatch.setattr("mirr.cli._is_interactive", lambda: True)
    interactive = runner.invoke(cli, ["del"], input="company\n")
    assert interactive.exit_code == 0, interactive.output
    assert "Index" in interactive.output


def test_injected_temporary_write_failure_leaves_original(
    tmp_path: Path,
    monkeypatch,
) -> None:
    path = tmp_path / "uv.toml"
    path.write_text('index-url = "https://old.example/simple"\n', encoding="utf-8")
    original = path.read_bytes()

    def fail_write(*args, **kwargs):
        raise OSError("injected write failure")

    monkeypatch.setattr("mirr.backends.uv.tempfile.NamedTemporaryFile", fail_write)

    with pytest.raises(ConfigEditorError, match="injected write failure"):
        set_default_index(LocalTarget(path, "uv", True), "https://new.example/simple")

    assert path.read_bytes() == original


def test_editor_writes_disable_platform_newline_translation(
    tmp_path: Path, monkeypatch
) -> None:
    """`tempfile.NamedTemporaryFile(mode="w")` defaults to translating '\\n' to
    os.linesep on write. tomlkit always renders '\\n'; without `newline=""` the
    same edit produces CRLF-terminated uv.toml/pyproject.toml files on Windows
    while Linux/macOS keep LF, so files written on one OS diverge from the
    other even though mirr made the identical edit."""

    path = tmp_path / "uv.toml"
    captured: dict = {}
    real_named_temporary_file = tempfile.NamedTemporaryFile

    def spy(*args, **kwargs):
        captured.update(kwargs)
        return real_named_temporary_file(*args, **kwargs)

    monkeypatch.setattr("mirr.backends.uv.tempfile.NamedTemporaryFile", spy)
    set_default_index(LocalTarget(path, "new", False), "https://pypi.org/simple")

    assert captured.get("newline") == ""


def test_catalog_writes_disable_platform_newline_translation(
    tmp_path: Path, monkeypatch
) -> None:
    path = tmp_path / "mirr.toml"
    captured: dict = {}
    real_named_temporary_file = tempfile.NamedTemporaryFile

    def spy(*args, **kwargs):
        captured.update(kwargs)
        return real_named_temporary_file(*args, **kwargs)

    monkeypatch.setattr("mirr.catalog.tempfile.NamedTemporaryFile", spy)
    CatalogStore(path).add("company", "https://packages.example.com/simple")

    assert captured.get("newline") == ""


@pytest.mark.parametrize(
    "error",
    [
        HTTPError("https://pypi.org/simple", 503, "unavailable", {}, None),
        URLError(ssl.SSLError("certificate verify failed")),
        TimeoutError("timed out"),
    ],
    ids=["http", "tls", "timeout"],
)
def test_probe_reports_http_tls_and_timeout_failures(error: OSError) -> None:
    def fail(request, timeout):
        raise error

    result = probe_index(Index("pypi", "https://pypi.org/simple"), opener=fail)

    assert not result.ok
    assert result.error


def test_probe_accepts_redirect_response() -> None:
    ticks = iter([1.0, 1.01])

    result = probe_index(
        Index("pypi", "https://pypi.org/simple"),
        opener=lambda request, timeout: RedirectResponse(),
        clock=lambda: next(ticks),
    )

    assert result.ok


def test_requested_browser_launch_failure_is_reported(tmp_path: Path) -> None:
    executable = tmp_path / "browser"
    executable.touch()

    def fail_launch(argv):
        raise OSError("launch failed")

    with pytest.raises(BrowserError, match="launch failed"):
        open_index_home(
            Index("pypi", "https://pypi.org/simple", "https://pypi.org"),
            browser=str(executable),
            launch=fail_launch,
        )


@pytest.mark.skipif(shutil.which("uv") is None, reason="uv binary not available")
@pytest.mark.parametrize("kind", ["uv", "pyproject"])
def test_written_config_is_accepted_by_real_uv(tmp_path: Path, kind: str) -> None:
    """`default-index` is only a uv CLI flag / env var name, never a config
    file field: uv rejects it with `unknown field` and refuses to run. mirr
    must write a key uv's TOML parser actually recognizes."""

    if kind == "uv":
        path = tmp_path / "uv.toml"
    else:
        path = tmp_path / "pyproject.toml"
        path.write_text('[project]\nname = "demo"\nversion = "0.1.0"\n', encoding="utf-8")

    set_default_index(LocalTarget(path, kind, path.exists()), "https://pypi.org/simple")

    env = dict(os.environ)
    if kind == "uv":
        env["UV_CONFIG_FILE"] = str(path)
    result = subprocess.run(
        ["uv", "pip", "list"],
        cwd=tmp_path,
        env=env,
        capture_output=True,
        text=True,
        timeout=30,
    )
    assert "unknown field" not in result.stderr, result.stderr

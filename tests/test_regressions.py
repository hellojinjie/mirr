from __future__ import annotations

import ssl
from pathlib import Path
from urllib.error import HTTPError, URLError

import pytest
from click.testing import CliRunner
from conftest import IsolatedEnvironment

from mirr.browser import BrowserError, open_index_home
from mirr.catalog import CatalogError, CatalogStore, Index, default_catalog_path
from mirr.cli import cli
from mirr.config import LocalTarget
from mirr.editor import ConfigEditorError, set_default_index
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
    assert default_catalog_path() == isolated_env.xdg_config / "mirr" / "config.toml"


def test_delete_protects_user_selection_even_when_project_overrides_it(
    isolated_env: IsolatedEnvironment,
) -> None:
    runner = CliRunner()
    assert (
        runner.invoke(cli, ["add", "company", "https://packages.example.com/simple"]).exit_code == 0
    )
    assert runner.invoke(cli, ["use", "company"]).exit_code == 0
    (isolated_env.project / "uv.toml").write_text(
        'default-index = "https://pypi.org/simple"\n', encoding="utf-8"
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
    path.write_text('default-index = "https://old.example/simple"\n', encoding="utf-8")
    original = path.read_bytes()

    def fail_write(*args, **kwargs):
        raise OSError("injected write failure")

    monkeypatch.setattr("mirr.editor.tempfile.NamedTemporaryFile", fail_write)

    with pytest.raises(ConfigEditorError, match="injected write failure"):
        set_default_index(LocalTarget(path, "uv", True), "https://new.example/simple")

    assert path.read_bytes() == original


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

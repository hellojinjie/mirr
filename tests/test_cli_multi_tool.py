from __future__ import annotations

from pathlib import Path

import pytest
from click.testing import CliRunner

from mirr.cli import _ALL_VERBS, SUPPORTED_TOOLS, cli


def test_bare_aliases_are_the_same_command_objects_as_mirr_uv() -> None:
    uv_group = cli.commands["uv"]
    for verb in _ALL_VERBS:
        assert cli.commands[verb] is uv_group.commands[verb]


def test_unknown_tool_reports_supported_tools_and_exits_nonzero() -> None:
    result = CliRunner().invoke(cli, ["foo", "ls"])

    assert result.exit_code != 0
    assert "not a supported tool" in result.output
    for tool in SUPPORTED_TOOLS:
        assert tool in result.output


def test_conda_help_lists_only_ls_and_test() -> None:
    result = CliRunner().invoke(cli, ["conda", "--help"])

    assert result.exit_code == 0, result.output
    assert "ls" in result.output
    assert "test" in result.output
    for hidden_verb in ("use", "add", "del", "rename", "home", "current"):
        assert hidden_verb not in result.output


@pytest.mark.parametrize(
    ("args", "match_all"),
    [
        (["conda", "use", "tsinghua"], ["not supported"]),
        (["conda", "add", "x", "https://example.com"], ["not supported"]),
        (["conda", "del", "x"], ["not supported"]),
        (["conda", "rename", "x", "y"], ["not supported"]),
        (["conda", "current"], ["not supported"]),
        (["conda", "home", "defaults"], ["not supported"]),
    ],
)
def test_conda_unsupported_verbs_report_clear_error(
    args: list[str], match_all: list[str]
) -> None:
    result = CliRunner().invoke(cli, args)

    assert result.exit_code != 0
    for expected in match_all:
        assert expected in result.output


def test_conda_ls_lists_builtins_without_marking_current(tmp_path: Path) -> None:
    result = CliRunner().invoke(cli, ["conda", "ls"])

    assert result.exit_code == 0, result.output
    assert "*" not in result.output
    assert "Current:" not in result.output
    assert "defaults" in result.output
    assert "tsinghua" in result.output


def test_pip_use_and_current_round_trip(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    home = tmp_path / "home"
    xdg = tmp_path / "xdg"
    for path in (home, xdg):
        path.mkdir()
    monkeypatch.setenv("HOME", str(home))
    monkeypatch.setenv("XDG_CONFIG_HOME", str(xdg))
    monkeypatch.delenv("VIRTUAL_ENV", raising=False)
    monkeypatch.delenv("PIP_INDEX_URL", raising=False)
    monkeypatch.chdir(tmp_path)

    runner = CliRunner()
    use_result = runner.invoke(cli, ["pip", "use", "tsinghua"])
    assert use_result.exit_code == 0, use_result.output

    pip_conf = xdg / "pip" / "pip.conf"
    assert "index-url = https://pypi.tuna.tsinghua.edu.cn/simple" in pip_conf.read_text(
        encoding="utf-8"
    )

    current_result = runner.invoke(cli, ["pip", "current"])
    assert current_result.exit_code == 0, current_result.output
    assert "tsinghua" in current_result.output


def test_pip_use_local_without_active_venv_fails_without_writing(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.setenv("HOME", str(tmp_path / "home"))
    monkeypatch.setenv("XDG_CONFIG_HOME", str(tmp_path / "xdg"))
    monkeypatch.delenv("VIRTUAL_ENV", raising=False)
    monkeypatch.chdir(tmp_path)

    result = CliRunner().invoke(cli, ["pip", "use", "tsinghua", "--local"])

    assert result.exit_code != 0
    assert "virtualenv" in result.output
    assert not any(tmp_path.rglob("pip.conf"))


def test_npm_use_local_writes_project_npmrc(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("HOME", str(tmp_path / "home"))
    monkeypatch.delenv("npm_config_registry", raising=False)
    monkeypatch.chdir(tmp_path)

    result = CliRunner().invoke(cli, ["npm", "use", "npmmirror", "--local", "--yes"])

    assert result.exit_code == 0, result.output
    npmrc = tmp_path / ".npmrc"
    assert npmrc.read_text(encoding="utf-8") == "registry=https://registry.npmmirror.com\n"


def test_npm_ls_marks_current_selection(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    home = tmp_path / "home"
    home.mkdir()
    monkeypatch.setenv("HOME", str(home))
    monkeypatch.delenv("npm_config_registry", raising=False)
    monkeypatch.chdir(tmp_path)
    (home / ".npmrc").write_text("registry=https://registry.npmmirror.com\n", encoding="utf-8")

    result = CliRunner().invoke(cli, ["npm", "ls"])

    assert result.exit_code == 0, result.output
    assert "* npmmirror" in result.output

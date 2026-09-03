from __future__ import annotations

from click.testing import CliRunner
from conftest import IsolatedEnvironment

from uim.cli import cli


def invoke_ok(runner: CliRunner, *args: str):
    result = runner.invoke(cli, list(args))
    assert result.exit_code == 0, result.output
    return result


def test_user_scope_catalog_and_switch_lifecycle(
    isolated_env: IsolatedEnvironment,
) -> None:
    runner = CliRunner()

    invoke_ok(runner, "add", "company", "https://packages.example.com/simple")
    invoke_ok(runner, "use", "company")
    assert invoke_ok(runner, "current").output.strip() == "You are using company index."
    assert "* company" in invoke_ok(runner, "ls").output

    invoke_ok(runner, "rename", "company", "internal")
    assert invoke_ok(runner, "current").output.strip() == "You are using internal index."

    invoke_ok(runner, "use", "pypi")
    invoke_ok(runner, "del", "internal")
    assert "internal" not in invoke_ok(runner, "ls").output
    assert (isolated_env.xdg_config / "uv" / "uv.toml").is_file()


def test_local_scope_catalog_and_switch_lifecycle(
    isolated_env: IsolatedEnvironment,
) -> None:
    runner = CliRunner()
    pyproject = isolated_env.project / "pyproject.toml"
    pyproject.write_text('[project]\nname = "demo"\n', encoding="utf-8")

    invoke_ok(runner, "add", "company", "https://packages.example.com/simple")
    invoke_ok(runner, "use", "company", "--local")
    assert invoke_ok(runner, "current").output.strip() == "You are using company index."
    assert "* company" in invoke_ok(runner, "ls").output

    invoke_ok(runner, "rename", "company", "internal")
    assert invoke_ok(runner, "current").output.strip() == "You are using internal index."

    invoke_ok(runner, "use", "pypi", "--local")
    invoke_ok(runner, "del", "internal")
    assert "internal" not in invoke_ok(runner, "ls").output
    assert not (isolated_env.xdg_config / "uv" / "uv.toml").exists()

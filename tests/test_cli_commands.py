from __future__ import annotations

import tomlkit
from click.testing import CliRunner
from conftest import IsolatedEnvironment

from mirr.catalog import CatalogStore
from mirr.cli import cli


def test_add_rename_and_delete_custom_index(isolated_env: IsolatedEnvironment) -> None:
    runner = CliRunner()

    result = runner.invoke(
        cli,
        [
            "add",
            "company",
            "https://packages.example.com/simple",
            "https://packages.example.com",
        ],
    )
    assert result.exit_code == 0, result.output
    store = CatalogStore(isolated_env.catalog_path)
    assert store.get("company").home == "https://packages.example.com"

    result = runner.invoke(cli, ["rename", "company", "internal"])
    assert result.exit_code == 0, result.output
    assert store.get("internal").url == "https://packages.example.com/simple"

    result = runner.invoke(cli, ["del", "internal"])
    assert result.exit_code == 0, result.output
    assert "internal" not in store.entries()


def test_catalog_command_errors_are_nonzero_and_do_not_mutate(
    isolated_env: IsolatedEnvironment,
) -> None:
    runner = CliRunner()

    result = runner.invoke(cli, ["del", "pypi"])

    assert result.exit_code != 0
    assert "built-in" in result.output
    assert not isolated_env.catalog_path.exists()


def test_global_use_writes_user_uv_config_and_reports_success(
    isolated_env: IsolatedEnvironment,
) -> None:
    result = CliRunner().invoke(cli, ["use", "tsinghua"])

    assert result.exit_code == 0, result.output
    assert "SUCCESS" in result.output
    assert "tsinghua" in result.output
    document = tomlkit.parse(
        isolated_env.user_uv_config.read_text(encoding="utf-8")
    )
    assert "index-url" not in document
    assert document["index"][0]["name"] == "tsinghua"
    assert document["index"][0]["url"] == "https://pypi.tuna.tsinghua.edu.cn/simple"
    assert document["index"][0]["default"] is True


def test_global_use_updates_simple_named_structured_default_in_place(
    isolated_env: IsolatedEnvironment,
) -> None:
    path = isolated_env.user_uv_config
    path.parent.mkdir(parents=True)
    path.write_text(
        "# keep this comment\n"
        "[[index]]\n"
        'name = "tsinghua"\n'
        'url = "https://pypi.tuna.tsinghua.edu.cn/simple"\n'
        "default = true\n",
        encoding="utf-8",
    )

    result = CliRunner().invoke(cli, ["use", "aliyun"])

    assert result.exit_code == 0, result.output
    content = path.read_text(encoding="utf-8")
    document = tomlkit.parse(content)
    assert "# keep this comment" in content
    assert "index-url" not in document
    assert len(document["index"]) == 1
    assert document["index"][0]["name"] == "aliyun"
    assert document["index"][0]["url"] == "https://mirrors.aliyun.com/pypi/simple"
    assert document["index"][0]["default"] is True


def test_global_use_warns_when_project_configuration_still_wins(
    isolated_env: IsolatedEnvironment,
) -> None:
    (isolated_env.project / "uv.toml").write_text(
        'index-url = "https://project.example/simple"\n', encoding="utf-8"
    )

    result = CliRunner().invoke(cli, ["use", "pypi"])

    assert result.exit_code == 0, result.output
    assert "Warning" in result.output
    assert "project:uv.toml" in result.output


def test_use_without_name_requires_a_tty(isolated_env: IsolatedEnvironment) -> None:
    result = CliRunner().invoke(cli, ["use"])

    assert result.exit_code != 0
    assert "index name is required" in result.output


def test_use_without_name_prompts_in_interactive_terminal(
    isolated_env: IsolatedEnvironment,
    monkeypatch,
) -> None:
    monkeypatch.setattr("mirr.cli._is_interactive", lambda: True)

    result = CliRunner().invoke(cli, ["use"], input="pypi\n")

    assert result.exit_code == 0, result.output
    assert "Index" in result.output
    assert "SUCCESS" in result.output


def test_local_use_updates_pyproject_without_writing_user_config(
    isolated_env: IsolatedEnvironment,
) -> None:
    pyproject = isolated_env.project / "pyproject.toml"
    pyproject.write_text('[project]\nname = "demo"\n', encoding="utf-8")

    result = CliRunner().invoke(cli, ["use", "aliyun", "--local"])

    assert result.exit_code == 0, result.output
    document = tomlkit.parse(pyproject.read_text(encoding="utf-8"))
    assert "index-url" not in document["tool"]["uv"]
    assert document["tool"]["uv"]["index"][0]["url"] == ("https://mirrors.aliyun.com/pypi/simple")
    assert document["tool"]["uv"]["index"][0]["default"] is True
    assert "name" not in document["tool"]["uv"]["index"][0]
    assert not isolated_env.user_uv_config.exists()


def test_repeated_global_use_keeps_a_single_structured_entry(
    isolated_env: IsolatedEnvironment,
) -> None:
    runner = CliRunner()
    assert runner.invoke(cli, ["use", "tsinghua"]).exit_code == 0
    assert runner.invoke(cli, ["use", "aliyun"]).exit_code == 0

    document = tomlkit.parse(isolated_env.user_uv_config.read_text(encoding="utf-8"))
    assert len(document["index"]) == 1
    assert document["index"][0]["name"] == "aliyun"
    assert document["index"][0]["url"] == "https://mirrors.aliyun.com/pypi/simple"


def test_repeated_local_use_keeps_a_single_anonymous_pyproject_entry(
    isolated_env: IsolatedEnvironment,
) -> None:
    pyproject = isolated_env.project / "pyproject.toml"
    pyproject.write_text('[project]\nname = "demo"\n', encoding="utf-8")
    runner = CliRunner()

    assert runner.invoke(cli, ["use", "tsinghua", "--local"]).exit_code == 0
    second = runner.invoke(cli, ["use", "aliyun", "--local"])
    assert second.exit_code == 0, second.output

    document = tomlkit.parse(pyproject.read_text(encoding="utf-8"))
    assert len(document["tool"]["uv"]["index"]) == 1
    assert document["tool"]["uv"]["index"][0]["url"] == "https://mirrors.aliyun.com/pypi/simple"
    assert "name" not in document["tool"]["uv"]["index"][0]


def test_new_local_use_requires_confirmation_or_yes(
    isolated_env: IsolatedEnvironment,
) -> None:
    runner = CliRunner()

    rejected = runner.invoke(cli, ["use", "pypi", "--local"])
    assert rejected.exit_code != 0
    assert "--yes" in rejected.output
    assert not (isolated_env.project / "uv.toml").exists()

    accepted = runner.invoke(cli, ["use", "pypi", "--local", "--yes"])
    assert accepted.exit_code == 0, accepted.output
    assert (isolated_env.project / "uv.toml").exists()
    assert not isolated_env.user_uv_config.exists()


def test_active_custom_index_cannot_be_deleted(isolated_env: IsolatedEnvironment) -> None:
    runner = CliRunner()
    assert (
        runner.invoke(cli, ["add", "company", "https://packages.example.com/simple"]).exit_code == 0
    )
    assert runner.invoke(cli, ["use", "company"]).exit_code == 0

    result = runner.invoke(cli, ["del", "company"])

    assert result.exit_code != 0
    assert "currently selected" in result.output


def test_current_reports_name_url_and_provenance(isolated_env: IsolatedEnvironment) -> None:
    runner = CliRunner()
    assert runner.invoke(cli, ["use", "tencent"]).exit_code == 0

    named = runner.invoke(cli, ["current"])
    url = runner.invoke(cli, ["current", "-u"])
    verbose = runner.invoke(cli, ["current", "--verbose"])

    assert named.output.strip() == "You are using tencent index."
    assert (
        url.output.strip() == "You are using https://mirrors.cloud.tencent.com/pypi/simple index."
    )
    assert "tencent" in verbose.output
    assert "user:uv.toml" in verbose.output


def test_current_displays_uncataloged_environment_url(
    isolated_env: IsolatedEnvironment,
    monkeypatch,
) -> None:
    monkeypatch.setenv("UV_DEFAULT_INDEX", "https://unknown.example/simple")

    result = CliRunner().invoke(cli, ["current"])

    assert result.exit_code == 0
    assert "Your current index(https://unknown.example/simple)" in result.output


def test_ls_marks_only_effective_catalog_entry(isolated_env: IsolatedEnvironment) -> None:
    result = CliRunner().invoke(cli, ["ls"])

    assert result.exit_code == 0
    assert result.output == (
        "* pypi     --- https://pypi.org/simple\n"
        "  tsinghua --- https://pypi.tuna.tsinghua.edu.cn/simple\n"
        "  aliyun   --- https://mirrors.aliyun.com/pypi/simple\n"
        "  tencent  --- https://mirrors.cloud.tencent.com/pypi/simple\n"
        "  huawei   --- https://repo.huaweicloud.com/repository/pypi/simple\n"
        "  ustc     --- https://mirrors.ustc.edu.cn/pypi/simple\n"
    )


def test_ls_reports_uncataloged_effective_url(
    isolated_env: IsolatedEnvironment,
    monkeypatch,
) -> None:
    monkeypatch.setenv("UV_DEFAULT_INDEX", "https://unknown.example/simple")

    result = CliRunner().invoke(cli, ["ls"])

    assert result.exit_code == 0
    assert not any(line.startswith("*") for line in result.output.splitlines())
    assert "Current: https://unknown.example/simple" in result.output

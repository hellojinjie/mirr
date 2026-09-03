from __future__ import annotations

from click.testing import CliRunner
from conftest import IsolatedEnvironment

from uim.cli import cli


def test_global_use_rejects_named_default_with_extra_semantics(
    isolated_env: IsolatedEnvironment,
) -> None:
    path = isolated_env.xdg_config / "uv" / "uv.toml"
    path.parent.mkdir(parents=True)
    path.write_text(
        "[[index]]\n"
        'name = "company"\n'
        'url = "https://company.example/simple"\n'
        "default = true\n"
        'authenticate = "always"\n',
        encoding="utf-8",
    )
    original = path.read_bytes()

    result = CliRunner().invoke(cli, ["use", "aliyun"])

    assert result.exit_code != 0
    assert "unmanaged semantics" in result.output
    assert path.read_bytes() == original


def test_local_use_rejects_named_pyproject_default(
    isolated_env: IsolatedEnvironment,
) -> None:
    path = isolated_env.project / "pyproject.toml"
    path.write_text(
        '[project]\nname = "demo"\n\n'
        "[[tool.uv.index]]\n"
        'name = "company"\n'
        'url = "https://company.example/simple"\n'
        "default = true\n",
        encoding="utf-8",
    )
    original = path.read_bytes()

    result = CliRunner().invoke(cli, ["use", "aliyun", "--local"])

    assert result.exit_code != 0
    assert "unmanaged semantics" in result.output
    assert path.read_bytes() == original


def test_global_use_rejects_duplicate_target_index_name(
    isolated_env: IsolatedEnvironment,
) -> None:
    path = isolated_env.xdg_config / "uv" / "uv.toml"
    path.parent.mkdir(parents=True)
    path.write_text(
        "[[index]]\n"
        'name = "tsinghua"\n'
        'url = "https://pypi.tuna.tsinghua.edu.cn/simple"\n'
        "default = true\n\n"
        "[[index]]\n"
        'name = "aliyun"\n'
        'url = "https://packages.example/simple"\n'
        "explicit = true\n",
        encoding="utf-8",
    )
    original = path.read_bytes()

    result = CliRunner().invoke(cli, ["use", "aliyun"])

    assert result.exit_code != 0
    assert "index name 'aliyun' already exists" in result.output
    assert path.read_bytes() == original

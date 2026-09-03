from __future__ import annotations

import os
from pathlib import Path

from conftest import IsolatedEnvironment


def test_isolated_environment_redirects_all_user_paths(
    isolated_env: IsolatedEnvironment,
) -> None:
    assert Path(os.environ["HOME"]) == isolated_env.home
    assert Path(os.environ["XDG_CONFIG_HOME"]) == isolated_env.xdg_config
    assert Path(os.environ["APPDATA"]) == isolated_env.appdata
    assert Path(os.environ["PROGRAMDATA"]) == isolated_env.programdata
    assert Path.cwd() == isolated_env.project
    assert "UV_DEFAULT_INDEX" not in os.environ
    assert "UV_INDEX_URL" not in os.environ


def test_malformed_config_fixture_is_inside_isolated_xdg_home(
    isolated_env: IsolatedEnvironment,
    malformed_uv_config: Path,
) -> None:
    assert malformed_uv_config == isolated_env.xdg_config / "uv" / "uv.toml"
    assert malformed_uv_config.read_text(encoding="utf-8") == 'default-index = "unterminated\n'

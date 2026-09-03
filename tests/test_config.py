from __future__ import annotations

from pathlib import Path

import pytest

from mirr.catalog import CatalogStore
from mirr.config import (
    ConfigError,
    find_local_target,
    match_catalog_name,
    resolve_effective_index,
    system_uv_config_paths,
    user_uv_config_path,
)


def test_user_uv_config_path_uses_xdg_on_linux(tmp_path: Path) -> None:
    env = {"XDG_CONFIG_HOME": str(tmp_path / "xdg")}

    assert user_uv_config_path(env=env, platform="linux", home=tmp_path / "home") == (
        tmp_path / "xdg" / "uv" / "uv.toml"
    )


def test_user_uv_config_path_falls_back_to_home_on_macos(tmp_path: Path) -> None:
    assert user_uv_config_path(env={}, platform="darwin", home=tmp_path / "home") == (
        tmp_path / "home" / ".config" / "uv" / "uv.toml"
    )


def test_user_and_system_uv_paths_use_windows_directories(tmp_path: Path) -> None:
    env = {
        "APPDATA": str(tmp_path / "appdata"),
        "PROGRAMDATA": str(tmp_path / "programdata"),
    }

    assert user_uv_config_path(env=env, platform="win32", home=tmp_path / "home") == (
        tmp_path / "appdata" / "uv" / "uv.toml"
    )
    assert system_uv_config_paths(env=env, platform="win32") == [
        tmp_path / "programdata" / "uv" / "uv.toml"
    ]


def test_system_uv_paths_prefer_xdg_directories_before_etc(tmp_path: Path) -> None:
    env = {"XDG_CONFIG_DIRS": f"{tmp_path / 'first'}:{tmp_path / 'second'}"}

    assert system_uv_config_paths(env=env, platform="linux") == [
        tmp_path / "first" / "uv" / "uv.toml",
        tmp_path / "second" / "uv" / "uv.toml",
        Path("/etc/uv/uv.toml"),
    ]


def test_local_target_prefers_an_existing_uv_toml(tmp_path: Path) -> None:
    project = tmp_path / "project"
    child = project / "packages" / "child"
    child.mkdir(parents=True)
    (project / "uv.toml").write_text("", encoding="utf-8")
    (child / "pyproject.toml").write_text("[project]\nname = 'child'\n", encoding="utf-8")

    target = find_local_target(child)

    assert target.path == project / "uv.toml"
    assert target.kind == "uv"
    assert target.exists


def test_local_target_uses_nearest_pyproject_when_no_uv_toml(tmp_path: Path) -> None:
    project = tmp_path / "project"
    child = project / "child"
    child.mkdir(parents=True)
    (project / "pyproject.toml").write_text("[project]\nname = 'root'\n", encoding="utf-8")
    (child / "pyproject.toml").write_text("[project]\nname = 'child'\n", encoding="utf-8")

    target = find_local_target(child)

    assert target.path == child / "pyproject.toml"
    assert target.kind == "pyproject"


def test_local_target_creates_uv_toml_in_unconfigured_directory(tmp_path: Path) -> None:
    target = find_local_target(tmp_path)

    assert target.path == tmp_path / "uv.toml"
    assert target.kind == "new"
    assert not target.exists


def test_effective_index_precedence_environment_project_user_system(tmp_path: Path) -> None:
    project = tmp_path / "project"
    project.mkdir()
    (project / "uv.toml").write_text(
        'default-index = "https://project.example/simple"\n', encoding="utf-8"
    )
    user = tmp_path / "user" / "uv.toml"
    user.parent.mkdir()
    user.write_text('default-index = "https://user.example/simple"\n', encoding="utf-8")
    system = tmp_path / "system" / "uv.toml"
    system.parent.mkdir()
    system.write_text('default-index = "https://system.example/simple"\n', encoding="utf-8")

    effective = resolve_effective_index(
        start=project,
        env={"UV_DEFAULT_INDEX": "https://env.example/simple"},
        user_config=user,
        system_configs=[system],
    )
    assert (effective.url, effective.source) == (
        "https://env.example/simple",
        "environment:UV_DEFAULT_INDEX",
    )

    effective = resolve_effective_index(
        start=project, env={}, user_config=user, system_configs=[system]
    )
    assert (effective.url, effective.source, effective.path) == (
        "https://project.example/simple",
        "project:uv.toml",
        project / "uv.toml",
    )

    (project / "uv.toml").write_text("preview = true\n", encoding="utf-8")
    effective = resolve_effective_index(
        start=project, env={}, user_config=user, system_configs=[system]
    )
    assert (effective.url, effective.source) == (
        "https://user.example/simple",
        "user:uv.toml",
    )

    user.unlink()
    effective = resolve_effective_index(
        start=project, env={}, user_config=user, system_configs=[system]
    )
    assert (effective.url, effective.source) == (
        "https://system.example/simple",
        "system:uv.toml",
    )


def test_effective_index_supports_legacy_and_structured_defaults(tmp_path: Path) -> None:
    project = tmp_path / "project"
    project.mkdir()
    pyproject = project / "pyproject.toml"
    pyproject.write_text(
        '[tool.uv]\nindex-url = "https://legacy.example/simple"\n', encoding="utf-8"
    )

    effective = resolve_effective_index(
        start=project, env={}, user_config=tmp_path / "missing", system_configs=[]
    )
    assert effective.url == "https://legacy.example/simple"

    pyproject.write_text(
        "[[tool.uv.index]]\n"
        'name = "company"\n'
        'url = "https://structured.example/simple"\n'
        "default = true\n",
        encoding="utf-8",
    )
    effective = resolve_effective_index(
        start=project, env={}, user_config=tmp_path / "missing", system_configs=[]
    )
    assert effective.url == "https://structured.example/simple"


def test_effective_index_defaults_to_pypi(tmp_path: Path) -> None:
    effective = resolve_effective_index(
        start=tmp_path, env={}, user_config=tmp_path / "missing", system_configs=[]
    )

    assert (effective.url, effective.source, effective.path) == (
        "https://pypi.org/simple",
        "implicit:pypi",
        None,
    )


def test_malformed_effective_config_reports_its_path(tmp_path: Path) -> None:
    config = tmp_path / "uv.toml"
    config.write_text('default-index = "unterminated\n', encoding="utf-8")

    with pytest.raises(ConfigError, match="uv.toml"):
        resolve_effective_index(
            start=tmp_path, env={}, user_config=tmp_path / "missing", system_configs=[]
        )


def test_catalog_matching_ignores_trailing_slash_but_preserves_unknown_url(tmp_path: Path) -> None:
    catalog = CatalogStore(tmp_path / "mirr.toml").entries()

    assert match_catalog_name("https://pypi.org/simple/", catalog) == "pypi"
    assert match_catalog_name("https://unknown.example/simple", catalog) is None

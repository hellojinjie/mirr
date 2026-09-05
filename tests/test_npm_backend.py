from __future__ import annotations

import os
import stat
from pathlib import Path

from mirr.backends.npm import (
    LocalTarget,
    NpmBackend,
    _apply_registry,
    find_local_target,
    managed_default_urls,
    registry_ping_url,
    resolve_effective_index,
    set_default_index,
    system_npmrc_paths,
    user_npmrc_path,
)
from mirr.catalog import Index


def test_user_npmrc_path_defaults_to_home(tmp_path: Path) -> None:
    assert user_npmrc_path(env={}, home=tmp_path / "home") == (tmp_path / "home" / ".npmrc")


def test_user_npmrc_path_honors_userconfig_override(tmp_path: Path) -> None:
    override = tmp_path / "custom" / ".npmrc"
    assert user_npmrc_path(env={"npm_config_userconfig": str(override)}) == override


def test_system_npmrc_paths_honors_prefix_override(tmp_path: Path) -> None:
    prefix = tmp_path / "prefix"
    assert system_npmrc_paths(env={"npm_config_prefix": str(prefix)}, platform="linux") == [
        prefix / "etc" / "npmrc"
    ]


def test_system_npmrc_paths_falls_back_to_platform_default(tmp_path: Path) -> None:
    assert system_npmrc_paths(env={}, platform="linux") == [
        Path("/usr/local/etc/npmrc")
    ]
    assert system_npmrc_paths(
        env={"APPDATA": str(tmp_path / "appdata")}, platform="win32"
    ) == [tmp_path / "appdata" / "npm" / "etc" / "npmrc"]


def test_find_local_target_targets_npmrc_in_current_directory(tmp_path: Path) -> None:
    target = find_local_target(tmp_path)

    assert target.path == tmp_path / ".npmrc"
    assert target.kind == "npmrc"
    assert not target.exists


def test_effective_registry_precedence_environment_project_user_global(tmp_path: Path) -> None:
    project = tmp_path / "project"
    project.mkdir()
    (project / ".npmrc").write_text("registry=https://project.example\n", encoding="utf-8")
    user = tmp_path / "user" / ".npmrc"
    user.parent.mkdir()
    user.write_text("registry=https://user.example\n", encoding="utf-8")
    system = tmp_path / "global" / "npmrc"
    system.parent.mkdir()
    system.write_text("registry=https://global.example\n", encoding="utf-8")

    effective = resolve_effective_index(
        start=project,
        env={"npm_config_registry": "https://env.example"},
        user_config=user,
        system_configs=[system],
    )
    assert (effective.url, effective.source) == (
        "https://env.example",
        "environment:npm_config_registry",
    )

    effective = resolve_effective_index(
        start=project, env={}, user_config=user, system_configs=[system]
    )
    assert (effective.url, effective.source, effective.path) == (
        "https://project.example",
        "project:.npmrc",
        project / ".npmrc",
    )

    (project / ".npmrc").write_text("save-exact=true\n", encoding="utf-8")
    effective = resolve_effective_index(
        start=project, env={}, user_config=user, system_configs=[system]
    )
    assert (effective.url, effective.source) == ("https://user.example", "user:.npmrc")

    user.unlink()
    effective = resolve_effective_index(
        start=project, env={}, user_config=user, system_configs=[system]
    )
    assert (effective.url, effective.source) == ("https://global.example", "global:npmrc")


def test_effective_registry_defaults_to_npmjs(tmp_path: Path) -> None:
    effective = resolve_effective_index(
        start=tmp_path, env={}, user_config=tmp_path / "missing", system_configs=[]
    )

    assert (effective.url, effective.source, effective.path) == (
        "https://registry.npmjs.org",
        "implicit:npmjs",
        None,
    )


def test_apply_registry_creates_new_file() -> None:
    assert _apply_registry("", "https://registry.npmmirror.com") == (
        "registry=https://registry.npmmirror.com\n"
    )


def test_apply_registry_preserves_unrelated_settings_scopes_and_comments() -> None:
    original = (
        "; keep this comment\n"
        "save-exact=true\n"
        "registry=https://old.example\n"
        "@corp:registry=https://corp.example/npm\n"
    )

    result = _apply_registry(original, "https://new.example")

    assert "; keep this comment" in result
    assert "save-exact=true" in result
    assert "@corp:registry=https://corp.example/npm" in result
    assert "registry=https://new.example" in result
    assert "https://old.example" not in result


def test_apply_registry_ignores_commented_registry_line() -> None:
    original = "# registry=https://commented.example\nsave-exact=true\n"

    result = _apply_registry(original, "https://new.example")

    assert "# registry=https://commented.example" in result
    assert "registry=https://new.example" in result


def test_set_default_index_writes_atomically_and_preserves_permissions(tmp_path: Path) -> None:
    path = tmp_path / ".npmrc"
    path.write_text("registry=https://old.example\n", encoding="utf-8")
    path.chmod(0o640)

    set_default_index(LocalTarget(path, "npmrc", True), "https://new.example")

    content = path.read_text(encoding="utf-8")
    assert "https://new.example" in content
    if os.name != "nt":
        assert stat.S_IMODE(path.stat().st_mode) == 0o640


def test_managed_default_urls_covers_project_and_user_scopes(tmp_path: Path, monkeypatch) -> None:
    home = tmp_path / "home"
    project = tmp_path / "project"
    project.mkdir()
    monkeypatch.setenv("HOME", str(home))
    monkeypatch.chdir(project)
    (project / ".npmrc").write_text("registry=https://project.example\n", encoding="utf-8")
    home.mkdir()
    (home / ".npmrc").write_text("registry=https://user.example\n", encoding="utf-8")

    assert managed_default_urls(start=project) == {
        "https://project.example",
        "https://user.example",
    }


def test_registry_ping_url_strips_trailing_slash() -> None:
    assert registry_ping_url("https://registry.npmjs.org") == "https://registry.npmjs.org/-/ping"
    assert registry_ping_url("https://registry.npmjs.org/") == "https://registry.npmjs.org/-/ping"


def test_npm_backend_supports_full_verb_set() -> None:
    assert NpmBackend.SUPPORTED_VERBS == frozenset(
        {"ls", "current", "use", "add", "del", "rename", "home", "test"}
    )


def test_npm_backend_build_probe_request_targets_ping_endpoint() -> None:
    backend = NpmBackend()
    index = Index("npmjs", "https://registry.npmjs.org")

    spec = backend.build_probe_request(index)

    assert spec.url == "https://registry.npmjs.org/-/ping"


def test_npm_backend_locate_targets_local_uses_project_npmrc(tmp_path: Path) -> None:
    target = NpmBackend().locate_targets(local=True, start=tmp_path)

    assert target.path == tmp_path / ".npmrc"
    assert target.kind == "npmrc"

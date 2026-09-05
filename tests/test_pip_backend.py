from __future__ import annotations

import configparser
import os
import stat
import sys
from pathlib import Path

import pytest

from mirr.backends.base import ConfigEditorError
from mirr.backends.pip import (
    LocalTarget,
    PipBackend,
    _apply_pip_index_url,
    find_local_target,
    managed_default_urls,
    resolve_effective_index,
    set_default_index,
    system_pip_config_paths,
    user_pip_config_path,
    venv_pip_config_path,
)
from mirr.catalog import Index


def test_user_pip_config_path_uses_xdg_on_linux(tmp_path: Path) -> None:
    assert user_pip_config_path(
        env={"XDG_CONFIG_HOME": str(tmp_path / "xdg")},
        platform="linux",
        home=tmp_path / "home",
    ) == (tmp_path / "xdg" / "pip" / "pip.conf")


def test_user_pip_config_path_uses_application_support_on_macos(tmp_path: Path) -> None:
    assert user_pip_config_path(env={}, platform="darwin", home=tmp_path / "home") == (
        tmp_path / "home" / "Library" / "Application Support" / "pip" / "pip.conf"
    )


def test_user_pip_config_path_uses_appdata_and_ini_on_windows(tmp_path: Path) -> None:
    assert user_pip_config_path(
        env={"APPDATA": str(tmp_path / "appdata")},
        platform="win32",
        home=tmp_path / "home",
    ) == (tmp_path / "appdata" / "pip" / "pip.ini")


def test_venv_pip_config_path_uses_conf_on_posix_and_ini_on_windows(tmp_path: Path) -> None:
    venv = tmp_path / "venv"
    assert venv_pip_config_path(venv, platform="linux") == venv / "pip.conf"
    assert venv_pip_config_path(venv, platform="win32") == venv / "pip.ini"


def test_system_pip_config_paths_per_platform(tmp_path: Path) -> None:
    assert system_pip_config_paths(env={}, platform="linux") == [Path("/etc/pip.conf")]
    assert system_pip_config_paths(env={}, platform="darwin") == [
        Path("/Library/Application Support/pip/pip.conf")
    ]
    assert system_pip_config_paths(
        env={"PROGRAMDATA": str(tmp_path / "programdata")}, platform="win32"
    ) == [tmp_path / "programdata" / "pip" / "pip.ini"]
    assert system_pip_config_paths(env={}, platform="win32") == []


def test_find_local_target_requires_active_virtualenv() -> None:
    with pytest.raises(ConfigEditorError, match="virtualenv"):
        find_local_target(env={}, platform="linux")


def test_find_local_target_uses_active_virtualenv(tmp_path: Path) -> None:
    venv = tmp_path / "venv"
    target = find_local_target(env={"VIRTUAL_ENV": str(venv)}, platform="linux")

    assert target.path == venv / "pip.conf"
    assert target.kind == "pip-venv"
    assert not target.exists


def test_effective_index_precedence_environment_venv_user_system(tmp_path: Path) -> None:
    venv = tmp_path / "venv"
    venv.mkdir()
    venv_config = venv_pip_config_path(venv, platform=sys.platform)
    venv_config.write_text(
        "[global]\nindex-url = https://venv.example/simple\n", encoding="utf-8"
    )
    user = tmp_path / "user" / "pip.conf"
    user.parent.mkdir()
    user.write_text("[global]\nindex-url = https://user.example/simple\n", encoding="utf-8")
    system = tmp_path / "system" / "pip.conf"
    system.parent.mkdir()
    system.write_text("[global]\nindex-url = https://system.example/simple\n", encoding="utf-8")

    effective = resolve_effective_index(
        start=tmp_path,
        env={"PIP_INDEX_URL": "https://env.example/simple", "VIRTUAL_ENV": str(venv)},
        user_config=user,
        system_configs=[system],
    )
    assert (effective.url, effective.source) == (
        "https://env.example/simple",
        "environment:PIP_INDEX_URL",
    )

    effective = resolve_effective_index(
        start=tmp_path,
        env={"VIRTUAL_ENV": str(venv)},
        user_config=user,
        system_configs=[system],
    )
    assert (effective.url, effective.source, effective.path) == (
        "https://venv.example/simple",
        "venv:pip.conf",
        venv_config,
    )

    effective = resolve_effective_index(
        start=tmp_path, env={}, user_config=user, system_configs=[system]
    )
    assert (effective.url, effective.source) == ("https://user.example/simple", "user:pip.conf")

    user.unlink()
    effective = resolve_effective_index(
        start=tmp_path, env={}, user_config=user, system_configs=[system]
    )
    assert (effective.url, effective.source) == (
        "https://system.example/simple",
        "system:pip.conf",
    )


def test_effective_index_defaults_to_pypi(tmp_path: Path) -> None:
    effective = resolve_effective_index(
        start=tmp_path, env={}, user_config=tmp_path / "missing", system_configs=[]
    )

    assert (effective.url, effective.source, effective.path) == (
        "https://pypi.org/simple",
        "implicit:pypi",
        None,
    )


def test_apply_pip_index_url_creates_global_section_when_missing() -> None:
    result = _apply_pip_index_url("", "https://pypi.org/simple")

    assert result == "[global]\nindex-url = https://pypi.org/simple\n"


def test_apply_pip_index_url_creates_global_section_after_existing_content() -> None:
    result = _apply_pip_index_url("[freeze]\ntimeout = 10\n", "https://pypi.org/simple")

    assert result == (
        "[freeze]\ntimeout = 10\n\n[global]\nindex-url = https://pypi.org/simple\n"
    )


def test_apply_pip_index_url_preserves_unrelated_settings_and_comments() -> None:
    original = (
        "# keep this comment\n"
        "[global]\n"
        "timeout = 10\n"
        "index-url = https://old.example/simple\n"
        "trusted-host = old.example\n\n"
        "[freeze]\n"
        "index-url = https://frozen.example/simple\n"
    )

    result = _apply_pip_index_url(original, "https://new.example/simple")

    assert "# keep this comment" in result
    assert "timeout = 10" in result
    assert "trusted-host = old.example" in result
    assert "index-url = https://new.example/simple" in result
    assert "https://old.example/simple" not in result
    # The [freeze] section's own index-url (a different section) is untouched.
    assert "index-url = https://frozen.example/simple" in result


def test_apply_pip_index_url_inserts_newline_when_global_header_is_last_line() -> None:
    # Regression: a `[global]` header with no trailing newline (end of file,
    # no key yet) must not have the new key concatenated directly onto it.
    result = _apply_pip_index_url("[global]", "https://pypi.org/simple")

    assert result == "[global]\nindex-url = https://pypi.org/simple\n"
    parser = configparser.ConfigParser()
    parser.read_string(result)
    assert parser.get("global", "index-url") == "https://pypi.org/simple"


def test_apply_pip_index_url_inserts_key_when_section_exists_without_it() -> None:
    result = _apply_pip_index_url("[global]\ntimeout = 10\n", "https://pypi.org/simple")

    # Inserted right after the section header; ordering within an INI
    # section is not semantically meaningful.
    assert result == "[global]\nindex-url = https://pypi.org/simple\ntimeout = 10\n"


def test_set_default_index_writes_atomically_and_preserves_permissions(tmp_path: Path) -> None:
    path = tmp_path / "pip.conf"
    path.write_text("[global]\nindex-url = https://old.example/simple\n", encoding="utf-8")
    path.chmod(0o640)

    set_default_index(LocalTarget(path, "pip-user", True), "https://new.example/simple")

    content = path.read_text(encoding="utf-8")
    assert "https://new.example/simple" in content
    if os.name != "nt":
        assert stat.S_IMODE(path.stat().st_mode) == 0o640


def test_managed_default_urls_covers_venv_and_user_scopes(tmp_path: Path, monkeypatch) -> None:
    home = tmp_path / "home"
    xdg = tmp_path / "xdg"
    appdata = tmp_path / "appdata"
    venv = tmp_path / "venv"
    venv.mkdir()
    monkeypatch.setenv("HOME", str(home))
    monkeypatch.setenv("XDG_CONFIG_HOME", str(xdg))
    monkeypatch.setenv("APPDATA", str(appdata))
    monkeypatch.setenv("VIRTUAL_ENV", str(venv))
    venv_config = venv_pip_config_path(venv, platform=sys.platform)
    venv_config.write_text(
        "[global]\nindex-url = https://venv.example/simple\n", encoding="utf-8"
    )
    user_path = user_pip_config_path()
    user_path.parent.mkdir(parents=True)
    user_path.write_text(
        "[global]\nindex-url = https://user.example/simple\n", encoding="utf-8"
    )

    assert managed_default_urls(start=tmp_path) == {
        "https://venv.example/simple",
        "https://user.example/simple",
    }


def test_pip_backend_supports_full_verb_set() -> None:
    assert PipBackend.SUPPORTED_VERBS == frozenset(
        {"ls", "current", "use", "add", "del", "rename", "home", "test"}
    )


def test_pip_backend_build_probe_request_reuses_simple_repository_endpoint() -> None:
    backend = PipBackend()
    index = Index("pypi", "https://pypi.org/simple")

    spec = backend.build_probe_request(index)

    assert spec.url == "https://pypi.org/simple/pip/"


def test_pip_backend_locate_targets_uses_user_scope_when_not_local(tmp_path: Path, monkeypatch) -> None:
    monkeypatch.setenv("HOME", str(tmp_path / "home"))
    monkeypatch.setenv("XDG_CONFIG_HOME", str(tmp_path / "xdg"))
    monkeypatch.setenv("APPDATA", str(tmp_path / "appdata"))

    target = PipBackend().locate_targets(local=False, start=tmp_path)

    assert target.path == user_pip_config_path()
    assert target.kind == "pip-user"

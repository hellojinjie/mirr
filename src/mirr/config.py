"""Discover and resolve uv configuration without invoking uv."""

from __future__ import annotations

import os
import sys
from collections.abc import Mapping, Sequence
from dataclasses import dataclass
from pathlib import Path
from typing import Optional

import tomlkit
from tomlkit.exceptions import TOMLKitError

from mirr.catalog import Index, normalize_url


class ConfigError(ValueError):
    """Raised when uv configuration cannot be interpreted safely."""


@dataclass(frozen=True)
class LocalTarget:
    path: Path
    kind: str
    exists: bool


@dataclass(frozen=True)
class EffectiveIndex:
    url: str
    source: str
    path: Optional[Path] = None


def user_uv_config_path(
    *,
    env: Optional[Mapping[str, str]] = None,
    platform: Optional[str] = None,
    home: Optional[Path] = None,
) -> Path:
    values = os.environ if env is None else env
    target_platform = sys.platform if platform is None else platform
    home_path = Path.home() if home is None else Path(home)
    if target_platform == "win32":
        base = Path(values.get("APPDATA", home_path / "AppData" / "Roaming"))
    else:
        base = Path(values.get("XDG_CONFIG_HOME", home_path / ".config"))
    return base / "uv" / "uv.toml"


def system_uv_config_paths(
    *,
    env: Optional[Mapping[str, str]] = None,
    platform: Optional[str] = None,
) -> list[Path]:
    values = os.environ if env is None else env
    target_platform = sys.platform if platform is None else platform
    if target_platform == "win32":
        programdata = values.get("PROGRAMDATA")
        return [Path(programdata) / "uv" / "uv.toml"] if programdata else []

    xdg_dirs = values.get("XDG_CONFIG_DIRS", "/etc/xdg")
    paths = [Path(item) / "uv" / "uv.toml" for item in xdg_dirs.split(":") if item]
    etc_path = Path("/etc/uv/uv.toml")
    if etc_path not in paths:
        paths.append(etc_path)
    return paths


def find_local_target(start: Path) -> LocalTarget:
    current = Path(start).resolve()
    if current.is_file():
        current = current.parent
    nearest_pyproject: Optional[Path] = None
    for directory in (current, *current.parents):
        uv_toml = directory / "uv.toml"
        if uv_toml.is_file():
            return LocalTarget(path=uv_toml, kind="uv", exists=True)
        pyproject = directory / "pyproject.toml"
        if nearest_pyproject is None and pyproject.is_file():
            nearest_pyproject = pyproject
    if nearest_pyproject is not None:
        return LocalTarget(path=nearest_pyproject, kind="pyproject", exists=True)
    return LocalTarget(path=current / "uv.toml", kind="new", exists=False)


def _load_document(path: Path):
    try:
        return tomlkit.parse(path.read_text(encoding="utf-8"))
    except (OSError, TOMLKitError) as exc:
        raise ConfigError(f"cannot read uv configuration {path}: {exc}") from exc


def _configured_default(path: Path, kind: str) -> Optional[str]:
    document = _load_document(path)
    if kind == "pyproject":
        tool = document.get("tool", {})
        settings = tool.get("uv", {}) if isinstance(tool, dict) else {}
    else:
        settings = document
    if not isinstance(settings, dict):
        raise ConfigError(f"uv settings must be a table in {path}")

    value = settings.get("index-url")
    if value is not None:
        return str(value)

    indexes = settings.get("index", [])
    defaults = [
        str(index["url"])
        for index in indexes
        if isinstance(index, dict) and index.get("default") is True and "url" in index
    ]
    if len(defaults) > 1:
        raise ConfigError(f"multiple indexes are marked as default in {path}")
    return defaults[0] if defaults else None


def resolve_effective_index(
    *,
    start: Path,
    env: Optional[Mapping[str, str]] = None,
    user_config: Optional[Path] = None,
    system_configs: Optional[Sequence[Path]] = None,
    platform: Optional[str] = None,
    home: Optional[Path] = None,
) -> EffectiveIndex:
    values = os.environ if env is None else env
    for variable in ("UV_DEFAULT_INDEX", "UV_INDEX_URL"):
        value = values.get(variable)
        if value:
            return EffectiveIndex(url=value, source=f"environment:{variable}")

    local = find_local_target(start)
    if local.exists:
        value = _configured_default(local.path, local.kind)
        if value is not None:
            return EffectiveIndex(
                url=value,
                source=f"project:{local.path.name}",
                path=local.path,
            )

    user_path = (
        user_uv_config_path(env=values, platform=platform, home=home)
        if user_config is None
        else Path(user_config)
    )
    if user_path.is_file():
        value = _configured_default(user_path, "uv")
        if value is not None:
            return EffectiveIndex(url=value, source="user:uv.toml", path=user_path)

    system_paths = (
        system_uv_config_paths(env=values, platform=platform)
        if system_configs is None
        else [Path(path) for path in system_configs]
    )
    for system_path in system_paths:
        if system_path.is_file():
            value = _configured_default(system_path, "uv")
            if value is not None:
                return EffectiveIndex(
                    url=value,
                    source="system:uv.toml",
                    path=system_path,
                )

    return EffectiveIndex(url="https://pypi.org/simple", source="implicit:pypi")


def managed_default_urls(*, start: Path, user_config: Optional[Path] = None) -> set[str]:
    """Return defaults in the user and project scopes that mirr can modify."""

    urls: set[str] = set()
    local = find_local_target(start)
    if local.exists:
        local_value = _configured_default(local.path, local.kind)
        if local_value is not None:
            urls.add(local_value)

    user_path = user_uv_config_path() if user_config is None else Path(user_config)
    if user_path.is_file():
        user_value = _configured_default(user_path, "uv")
        if user_value is not None:
            urls.add(user_value)

    return urls


def match_catalog_name(url: str, entries: Mapping[str, Index]) -> Optional[str]:
    normalized = normalize_url(url)
    for name, index in entries.items():
        if normalize_url(index.url) == normalized:
            return name
    return None

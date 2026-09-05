"""pip backend: discover, resolve, and edit pip's `index-url` without invoking pip.

pip has no project-level config, only user/venv/system scopes, so `--local`
here maps to the active virtualenv rather than a file in the current
directory.
"""

from __future__ import annotations

import configparser
import os
import re
import sys
from collections.abc import Mapping, Sequence
from pathlib import Path
from typing import Optional

from mirr.backends.base import (
    ConfigEditorError,
    ConfigError,
    EffectiveIndex,
    LocalTarget,
    ProbeSpec,
    atomic_write,
)
from mirr.catalog import Index
from mirr.probe import simple_repository_probe_url

SUPPORTED_VERBS = frozenset({"ls", "current", "use", "add", "del", "rename", "home", "test"})


def user_pip_config_path(
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
        return base / "pip" / "pip.ini"
    if target_platform == "darwin":
        # pip itself only uses Application Support when that directory
        # already exists, otherwise it falls back to a hardcoded ~/.config
        # (not honoring $XDG_CONFIG_HOME even on this fallback) - see
        # pip._internal.utils.appdirs._macos_user_config_dir.
        app_support = home_path / "Library" / "Application Support" / "pip"
        if app_support.is_dir():
            return app_support / "pip.conf"
        return home_path / ".config" / "pip" / "pip.conf"
    base = Path(values.get("XDG_CONFIG_HOME", home_path / ".config"))
    return base / "pip" / "pip.conf"


def venv_pip_config_path(venv: Path, *, platform: Optional[str] = None) -> Path:
    target_platform = sys.platform if platform is None else platform
    filename = "pip.ini" if target_platform == "win32" else "pip.conf"
    return Path(venv) / filename


def system_pip_config_paths(
    *,
    env: Optional[Mapping[str, str]] = None,
    platform: Optional[str] = None,
) -> list[Path]:
    values = os.environ if env is None else env
    target_platform = sys.platform if platform is None else platform
    if target_platform == "win32":
        programdata = values.get("PROGRAMDATA")
        return [Path(programdata) / "pip" / "pip.ini"] if programdata else []
    if target_platform == "darwin":
        return [Path("/Library/Application Support/pip/pip.conf")]
    return [Path("/etc/pip.conf")]


def _read_index_url(path: Path) -> Optional[str]:
    parser = configparser.ConfigParser()
    try:
        read_files = parser.read(path, encoding="utf-8")
    except configparser.Error as exc:
        raise ConfigError(f"cannot read pip configuration {path}: {exc}") from exc
    if not read_files:
        return None
    if parser.has_option("global", "index-url"):
        return parser.get("global", "index-url")
    return None


def find_local_target(
    *,
    env: Optional[Mapping[str, str]] = None,
    platform: Optional[str] = None,
) -> LocalTarget:
    """pip has no project-level config; `--local` maps to the active virtualenv."""

    values = os.environ if env is None else env
    venv = values.get("VIRTUAL_ENV")
    if not venv:
        raise ConfigEditorError(
            "--local requires an active virtualenv "
            "(pip has no project-level config; activate one first, or drop --local)"
        )
    path = venv_pip_config_path(Path(venv), platform=platform)
    return LocalTarget(path=path, kind="pip-venv", exists=path.is_file())


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
    value = values.get("PIP_INDEX_URL")
    if value:
        return EffectiveIndex(url=value, source="environment:PIP_INDEX_URL")

    venv = values.get("VIRTUAL_ENV")
    if venv:
        venv_path = venv_pip_config_path(Path(venv), platform=platform)
        if venv_path.is_file():
            value = _read_index_url(venv_path)
            if value is not None:
                return EffectiveIndex(url=value, source="venv:pip.conf", path=venv_path)

    user_path = (
        user_pip_config_path(env=values, platform=platform, home=home)
        if user_config is None
        else Path(user_config)
    )
    if user_path.is_file():
        value = _read_index_url(user_path)
        if value is not None:
            return EffectiveIndex(url=value, source="user:pip.conf", path=user_path)

    system_paths = (
        system_pip_config_paths(env=values, platform=platform)
        if system_configs is None
        else [Path(path) for path in system_configs]
    )
    for system_path in system_paths:
        if system_path.is_file():
            value = _read_index_url(system_path)
            if value is not None:
                return EffectiveIndex(url=value, source="system:pip.conf", path=system_path)

    return EffectiveIndex(url="https://pypi.org/simple", source="implicit:pypi")


def managed_default_urls(*, start: Path) -> set[str]:
    """Return defaults in the venv and user scopes that mirr can modify."""

    urls: set[str] = set()
    venv = os.environ.get("VIRTUAL_ENV")
    if venv:
        venv_path = venv_pip_config_path(Path(venv))
        if venv_path.is_file():
            value = _read_index_url(venv_path)
            if value is not None:
                urls.add(value)

    user_path = user_pip_config_path()
    if user_path.is_file():
        value = _read_index_url(user_path)
        if value is not None:
            urls.add(value)

    return urls


_SECTION_RE = re.compile(r"^\s*\[([^\]]*)\]\s*$")
_INDEX_URL_RE = re.compile(r"^\s*index-url\s*=")


def _apply_pip_index_url(text: str, url: str) -> str:
    """Set `index-url` under `[global]`, touching only that one line.

    Every other line - unrelated settings, comments, other sections - is
    copied through untouched, which is how this stays comment-preserving
    without a full INI round-trip library (see design.md, Decision 4).
    """

    lines = text.splitlines(keepends=True) if text else []
    global_start: Optional[int] = None
    key_line: Optional[int] = None
    in_global = False
    for index, line in enumerate(lines):
        section_match = _SECTION_RE.match(line)
        if section_match:
            if in_global:
                break
            in_global = section_match.group(1).strip().lower() == "global"
            if in_global:
                global_start = index
            continue
        if in_global and key_line is None and _INDEX_URL_RE.match(line):
            key_line = index

    new_line = f"index-url = {url}\n"
    if global_start is None:
        text_so_far = "".join(lines)
        if text_so_far and not text_so_far.endswith("\n"):
            text_so_far += "\n"
        if text_so_far:
            text_so_far += "\n"
        return text_so_far + f"[global]\n{new_line}"
    if key_line is not None:
        lines[key_line] = new_line
        return "".join(lines)
    if not lines[global_start].endswith("\n"):
        lines[global_start] += "\n"
    lines.insert(global_start + 1, new_line)
    return "".join(lines)


def set_default_index(target: LocalTarget, url: str) -> None:
    """Set pip's `index-url` and atomically replace the target file."""

    try:
        text = target.path.read_text(encoding="utf-8") if target.exists else ""
    except OSError as exc:
        raise ConfigEditorError(f"cannot read pip configuration {target.path}: {exc}") from exc
    updated = _apply_pip_index_url(text, url)
    atomic_write(target.path, updated)


class PipBackend:
    """`Backend` protocol implementation for pip (see `mirr.backends.base.Backend`)."""

    tool = "pip"
    SUPPORTED_VERBS = SUPPORTED_VERBS

    def locate_targets(self, *, local: bool, start: Path) -> LocalTarget:
        if local:
            return find_local_target()
        path = user_pip_config_path()
        return LocalTarget(path=path, kind="pip-user", exists=path.is_file())

    def resolve_effective(self, *, start: Path) -> EffectiveIndex:
        return resolve_effective_index(start=start)

    def apply_default(
        self, target: LocalTarget, url: str, *, index_name: Optional[str] = None
    ) -> None:
        set_default_index(target, url)

    def build_probe_request(self, index: Index) -> ProbeSpec:
        return ProbeSpec(url=simple_repository_probe_url(index.url))

    def managed_urls(self, *, start: Path) -> set[str]:
        return managed_default_urls(start=start)

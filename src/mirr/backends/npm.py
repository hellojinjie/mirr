"""npm backend: discover, resolve, and edit npm's `registry` without invoking npm.

Unlike uv, npm's project config (`.npmrc`) always lives directly in the
current directory - npm does not search parent directories for it - so
`find_local_target` mirrors that rather than uv's upward search.
"""

from __future__ import annotations

import os
import re
import sys
from collections.abc import Mapping, Sequence
from pathlib import Path
from typing import Optional

from mirr.backends.base import (
    ConfigEditorError,
    EffectiveIndex,
    LocalTarget,
    ProbeSpec,
    atomic_write,
)
from mirr.catalog import Index

SUPPORTED_VERBS = frozenset({"ls", "current", "use", "add", "del", "rename", "home", "test"})


def user_npmrc_path(
    *,
    env: Optional[Mapping[str, str]] = None,
    home: Optional[Path] = None,
) -> Path:
    values = os.environ if env is None else env
    override = values.get("npm_config_userconfig")
    if override:
        return Path(override)
    home_path = Path.home() if home is None else Path(home)
    return home_path / ".npmrc"


def system_npmrc_paths(
    *,
    env: Optional[Mapping[str, str]] = None,
    platform: Optional[str] = None,
    home: Optional[Path] = None,
) -> list[Path]:
    """Best-effort location of npm's global config, without invoking npm.

    npm resolves this from its own installation prefix, which mirr has no
    static, invocation-free way to determine; this honors an explicit
    `npm_config_prefix`/`NPM_CONFIG_PREFIX` override and otherwise falls back
    to npm's documented per-platform default prefix.
    """

    values = os.environ if env is None else env
    target_platform = sys.platform if platform is None else platform
    prefix = values.get("npm_config_prefix") or values.get("NPM_CONFIG_PREFIX")
    if prefix:
        base = Path(prefix)
    elif target_platform == "win32":
        home_path = Path.home() if home is None else Path(home)
        base = Path(values.get("APPDATA", home_path / "AppData" / "Roaming")) / "npm"
    else:
        base = Path("/usr/local")
    return [base / "etc" / "npmrc"]


def find_local_target(start: Path) -> LocalTarget:
    path = Path(start) / ".npmrc"
    return LocalTarget(path=path, kind="npmrc", exists=path.is_file())


_COMMENT_PREFIXES = ("#", ";")
_REGISTRY_RE = re.compile(r"^\s*registry\s*=\s*(.*?)\s*$")


def _read_registry(path: Path) -> Optional[str]:
    try:
        text = path.read_text(encoding="utf-8")
    except OSError:
        return None
    value: Optional[str] = None
    for line in text.splitlines():
        if line.lstrip().startswith(_COMMENT_PREFIXES):
            continue
        match = _REGISTRY_RE.match(line)
        if match:
            value = match.group(1)
    return value or None


def resolve_effective_index(
    *,
    start: Path,
    env: Optional[Mapping[str, str]] = None,
    user_config: Optional[Path] = None,
    system_configs: Optional[Sequence[Path]] = None,
    home: Optional[Path] = None,
) -> EffectiveIndex:
    values = os.environ if env is None else env
    value = values.get("npm_config_registry")
    if value:
        return EffectiveIndex(url=value, source="environment:npm_config_registry")

    project_path = Path(start) / ".npmrc"
    if project_path.is_file():
        value = _read_registry(project_path)
        if value is not None:
            return EffectiveIndex(url=value, source="project:.npmrc", path=project_path)

    user_path = (
        user_npmrc_path(env=values, home=home) if user_config is None else Path(user_config)
    )
    if user_path.is_file():
        value = _read_registry(user_path)
        if value is not None:
            return EffectiveIndex(url=value, source="user:.npmrc", path=user_path)

    system_paths = (
        system_npmrc_paths(env=values, home=home)
        if system_configs is None
        else [Path(path) for path in system_configs]
    )
    for system_path in system_paths:
        if system_path.is_file():
            value = _read_registry(system_path)
            if value is not None:
                return EffectiveIndex(url=value, source="global:npmrc", path=system_path)

    return EffectiveIndex(url="https://registry.npmjs.org", source="implicit:npmjs")


def managed_default_urls(*, start: Path) -> set[str]:
    """Return defaults in the project and user scopes that mirr can modify."""

    urls: set[str] = set()
    project_path = Path(start) / ".npmrc"
    if project_path.is_file():
        value = _read_registry(project_path)
        if value is not None:
            urls.add(value)

    user_path = user_npmrc_path()
    if user_path.is_file():
        value = _read_registry(user_path)
        if value is not None:
            urls.add(value)

    return urls


def _apply_registry(text: str, url: str) -> str:
    """Set the top-level `registry`, touching only that one line.

    Scoped overrides (`@corp:registry=...`) do not match the bare `registry`
    key and are left untouched, same as every other unrelated line.
    """

    lines = text.splitlines(keepends=True) if text else []
    key_line: Optional[int] = None
    for index, line in enumerate(lines):
        if line.lstrip().startswith(_COMMENT_PREFIXES):
            continue
        if _REGISTRY_RE.match(line):
            key_line = index

    new_line = f"registry={url}\n"
    if key_line is not None:
        lines[key_line] = new_line
        return "".join(lines)

    text_so_far = "".join(lines)
    if text_so_far and not text_so_far.endswith("\n"):
        text_so_far += "\n"
    return text_so_far + new_line


def set_default_index(target: LocalTarget, url: str) -> None:
    """Set npm's `registry` and atomically replace the target file."""

    try:
        text = target.path.read_text(encoding="utf-8") if target.exists else ""
    except OSError as exc:
        raise ConfigEditorError(f"cannot read npm configuration {target.path}: {exc}") from exc
    updated = _apply_registry(text, url)
    atomic_write(target.path, updated)


def registry_ping_url(registry_url: str) -> str:
    """npm registry protocol's own lightweight health-check endpoint."""

    return registry_url.rstrip("/") + "/-/ping"


class NpmBackend:
    """`Backend` protocol implementation for npm (see `mirr.backends.base.Backend`)."""

    tool = "npm"
    SUPPORTED_VERBS = SUPPORTED_VERBS

    def locate_targets(self, *, local: bool, start: Path) -> LocalTarget:
        if local:
            return find_local_target(start)
        path = user_npmrc_path()
        return LocalTarget(path=path, kind="npmrc-user", exists=path.is_file())

    def resolve_effective(self, *, start: Path) -> EffectiveIndex:
        return resolve_effective_index(start=start)

    def apply_default(
        self, target: LocalTarget, url: str, *, index_name: Optional[str] = None
    ) -> None:
        set_default_index(target, url)

    def build_probe_request(self, index: Index) -> ProbeSpec:
        return ProbeSpec(url=registry_ping_url(index.url))

    def managed_urls(self, *, start: Path) -> set[str]:
        return managed_default_urls(start=start)

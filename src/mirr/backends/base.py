"""Shared protocol every tool-specific backend (uv, pip, npm, conda, ...) implements.

A backend owns the parts of mirr that genuinely differ per tool: where its
config lives, how its effective value is resolved across scopes, how a
default gets written atomically, and what URL to hit when probing an entry
for reachability. Tool-agnostic pieces (the catalog CRUD store, the shared
HEAD/GET/Range probe loop, URL validation) live outside any single backend
and are reused by all of them.
"""

from __future__ import annotations

import os
import stat
import tempfile
from dataclasses import dataclass
from pathlib import Path
from typing import Optional, Protocol

from mirr.catalog import Index


class ConfigError(ValueError):
    """Raised when a tool's configuration cannot be interpreted safely."""


class ConfigEditorError(ValueError):
    """Raised when a tool's configuration cannot be changed safely."""


@dataclass(frozen=True)
class LocalTarget:
    """A config file a backend can write a default index/registry into."""

    path: Path
    kind: str
    exists: bool


@dataclass(frozen=True)
class EffectiveIndex:
    """The index/registry a backend currently resolves to for a given directory."""

    url: str
    source: str
    path: Optional[Path] = None


@dataclass(frozen=True)
class ProbeSpec:
    """Where to probe a catalog entry for reachability."""

    url: str


class Backend(Protocol):
    """What each tool-specific backend supplies to the shared CLI plumbing."""

    tool: str
    SUPPORTED_VERBS: frozenset[str]

    def locate_targets(self, *, local: bool, start: Path) -> LocalTarget:
        """Return where a `use` for this scope would write."""
        ...

    def resolve_effective(self, *, start: Path) -> EffectiveIndex:
        """Return the index/registry currently in effect for `start`."""
        ...

    def apply_default(
        self, target: LocalTarget, url: str, *, index_name: Optional[str] = None
    ) -> None:
        """Atomically set `url` as the default at `target`."""
        ...

    def build_probe_request(self, index: Index) -> ProbeSpec:
        """Return the request `mirr.probe` should issue to reach `index`."""
        ...

    def managed_urls(self, *, start: Path) -> set[str]:
        """Return URLs currently selected in scopes this backend can write to.

        Used to refuse deleting a catalog entry that's still the active
        selection somewhere mirr manages (user/project/venv scope) - not the
        full `resolve_effective` precedence, which also covers env vars and
        system scope that mirr never writes to.
        """
        ...


def atomic_write(path: Path, content: str) -> None:
    """Atomically replace `path` with `content`, preserving permissions if it exists.

    Shared by backends that hand-roll their target-file edits (see pip/npm)
    instead of going through a round-trip library like tomlkit.
    """

    path.parent.mkdir(parents=True, exist_ok=True)
    existing_mode = stat.S_IMODE(path.stat().st_mode) if path.exists() else None
    temporary: Optional[Path] = None
    try:
        with tempfile.NamedTemporaryFile(
            mode="w",
            encoding="utf-8",
            newline="",
            dir=path.parent,
            prefix=f".{path.name}.",
            delete=False,
        ) as handle:
            temporary = Path(handle.name)
            handle.write(content)
            handle.flush()
            os.fsync(handle.fileno())
        if existing_mode is not None:
            os.chmod(temporary, existing_mode)
        os.replace(temporary, path)
        temporary = None
        try:
            directory_fd = os.open(str(path.parent), os.O_RDONLY)
        except OSError:
            directory_fd = None
        if directory_fd is not None:
            try:
                os.fsync(directory_fd)
            finally:
                os.close(directory_fd)
    except OSError as exc:
        raise ConfigEditorError(f"cannot replace configuration {path}: {exc}") from exc
    finally:
        if temporary is not None:
            try:
                temporary.unlink()
            except FileNotFoundError:
                pass

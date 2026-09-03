"""Transactional, comment-preserving uv configuration edits."""

from __future__ import annotations

import os
import stat
import tempfile
from pathlib import Path
from typing import Callable, Optional

import tomlkit
from tomlkit.exceptions import TOMLKitError

from mirr.config import LocalTarget


class ConfigEditorError(ValueError):
    """Raised when a uv configuration cannot be changed safely."""


ReplaceFunction = Callable[[Path, Path], object]


def _document_for(target: LocalTarget):
    if not target.exists:
        return tomlkit.document()
    try:
        return tomlkit.parse(target.path.read_text(encoding="utf-8"))
    except (OSError, TOMLKitError) as exc:
        raise ConfigEditorError(f"cannot parse uv configuration {target.path}: {exc}") from exc


def _settings_table(document, target: LocalTarget):
    if target.kind != "pyproject":
        return document
    tool = document.get("tool")
    if tool is None:
        tool = tomlkit.table()
        document.add("tool", tool)
    if not isinstance(tool, dict):
        raise ConfigEditorError(f"tool must be a table in {target.path}")
    settings = tool.get("uv")
    if settings is None:
        settings = tomlkit.table()
        tool.add("uv", settings)
    if not isinstance(settings, dict):
        raise ConfigEditorError(f"tool.uv must be a table in {target.path}")
    return settings


def _name_collision(indexes, index_name: str, *, skip_position: Optional[int] = None) -> bool:
    return any(
        position != skip_position and isinstance(candidate, dict) and candidate.get("name") == index_name
        for position, candidate in enumerate(indexes)
    )


def _apply_structured_default(
    settings,
    target: LocalTarget,
    url: str,
    index_name: Optional[str],
) -> None:
    """Create or update the single `[[index]] default = true` entry.

    uv treats `[[index]] default = true` as the recommended way to select a
    default index (`index-url` is the legacy scalar form), so this is always
    mirr's write target; the scalar is only ever read for backward compatibility.

    `pyproject.toml` is commonly shared and reviewed by a team, so mirr never
    attaches a `name` there itself and refuses to touch an existing named
    default automatically; the user-level `uv.toml` is personal, so mirr may
    name and rename its entry freely.
    """

    name = index_name if target.kind != "pyproject" else None

    indexes = settings.get("index")
    defaults = (
        [
            position
            for position, index in enumerate(indexes)
            if isinstance(index, dict) and index.get("default") is True
        ]
        if indexes is not None
        else []
    )
    if len(defaults) > 1:
        raise ConfigEditorError(f"multiple structured default indexes in {target.path}")

    if defaults:
        position = defaults[0]
        entry = indexes[position]
        if set(entry.keys()) - {"name", "url", "default"}:
            raise ConfigEditorError(
                f"structured default index in {target.path} has unmanaged semantics; "
                "remove or migrate it explicitly"
            )
        if "name" in entry and (target.kind == "pyproject" or name is None):
            raise ConfigEditorError(
                f"structured default index in {target.path} has unmanaged semantics; "
                "remove or migrate it explicitly"
            )
        if name is not None:
            if _name_collision(indexes, name, skip_position=position):
                raise ConfigEditorError(
                    f"cannot switch structured default index in {target.path}: "
                    f"index name {name!r} already exists"
                )
            entry["name"] = name
        entry["url"] = url
        return

    if name is not None and indexes is not None and _name_collision(indexes, name):
        raise ConfigEditorError(
            f"cannot add structured default index in {target.path}: "
            f"index name {name!r} already exists"
        )
    entry = tomlkit.table()
    if name is not None:
        entry.add("name", name)
    entry.add("url", url)
    entry.add("default", True)
    if indexes is None:
        indexes = tomlkit.aot()
        settings.add("index", indexes)
    indexes.append(entry)


def set_default_index(
    target: LocalTarget,
    url: str,
    *,
    index_name: Optional[str] = None,
    replace: ReplaceFunction = os.replace,
) -> None:
    """Set one default index and atomically replace the target file."""

    document = _document_for(target)
    settings = _settings_table(document, target)
    _apply_structured_default(settings, target, url, index_name)
    if "index-url" in settings:
        del settings["index-url"]

    try:
        rendered = tomlkit.dumps(document)
        tomlkit.parse(rendered)
    except TOMLKitError as exc:
        raise ConfigEditorError(f"cannot render uv configuration {target.path}: {exc}") from exc

    target.path.parent.mkdir(parents=True, exist_ok=True)
    existing_mode = stat.S_IMODE(target.path.stat().st_mode) if target.path.exists() else None
    temporary: Optional[Path] = None
    try:
        with tempfile.NamedTemporaryFile(
            mode="w",
            encoding="utf-8",
            newline="",
            dir=target.path.parent,
            prefix=f".{target.path.name}.",
            delete=False,
        ) as handle:
            temporary = Path(handle.name)
            handle.write(rendered)
            handle.flush()
            os.fsync(handle.fileno())
        if existing_mode is not None:
            os.chmod(temporary, existing_mode)
        replace(temporary, target.path)
        temporary = None
        try:
            directory_fd = os.open(str(target.path.parent), os.O_RDONLY)
        except OSError:
            directory_fd = None
        if directory_fd is not None:
            try:
                os.fsync(directory_fd)
            finally:
                os.close(directory_fd)
    except OSError as exc:
        raise ConfigEditorError(f"cannot replace uv configuration {target.path}: {exc}") from exc
    finally:
        if temporary is not None:
            try:
                temporary.unlink()
            except FileNotFoundError:
                pass

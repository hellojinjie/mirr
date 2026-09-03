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


def _update_or_remove_safe_structured_default(
    settings,
    target: LocalTarget,
    url: str,
    index_name: Optional[str],
) -> bool:
    """Update a simple named user default, or remove a simple anonymous one."""

    indexes = settings.get("index")
    if indexes is None:
        return False
    defaults = [
        position
        for position, index in enumerate(indexes)
        if isinstance(index, dict) and index.get("default") is True
    ]
    if not defaults:
        return False
    if len(defaults) > 1:
        raise ConfigEditorError(f"multiple structured default indexes in {target.path}")
    position = defaults[0]
    entry = indexes[position]
    if set(entry.keys()) - {"name", "url", "default"}:
        raise ConfigEditorError(
            f"structured default index in {target.path} has unmanaged semantics; "
            "remove or migrate it explicitly"
        )

    if "name" in entry:
        if target.kind == "pyproject" or index_name is None:
            raise ConfigEditorError(
                f"structured default index in {target.path} has unmanaged semantics; "
                "remove or migrate it explicitly"
            )
        duplicate = any(
            candidate_position != position
            and isinstance(candidate, dict)
            and candidate.get("name") == index_name
            for candidate_position, candidate in enumerate(indexes)
        )
        if duplicate:
            raise ConfigEditorError(
                f"cannot switch structured default index in {target.path}: "
                f"index name {index_name!r} already exists"
            )
        entry["name"] = index_name
        entry["url"] = url
        return True

    del indexes[position]
    if not indexes:
        del settings["index"]
    return False


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
    uses_structured_default = _update_or_remove_safe_structured_default(
        settings, target, url, index_name
    )
    if "index-url" in settings:
        del settings["index-url"]
    if uses_structured_default:
        if "default-index" in settings:
            del settings["default-index"]
    else:
        settings["default-index"] = url

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

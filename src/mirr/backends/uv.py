"""uv backend: discover, resolve, and edit uv configuration without invoking uv."""

from __future__ import annotations

import os
import stat
import sys
import tempfile
from collections.abc import Mapping, Sequence
from pathlib import Path
from typing import Callable, Optional

import tomlkit
from tomlkit.exceptions import TOMLKitError

from mirr.backends.base import (
    ConfigEditorError,
    ConfigError,
    EffectiveIndex,
    LocalTarget,
    ProbeSpec,
)
from mirr.catalog import Index
from mirr.probe import simple_repository_probe_url

SUPPORTED_VERBS = frozenset({"ls", "current", "use", "add", "del", "rename", "home", "test"})

# Re-exported for backward compatibility: these used to be defined here.
__all__ = [
    "ConfigEditorError",
    "ConfigError",
    "SUPPORTED_VERBS",
    "UvBackend",
    "find_local_target",
    "managed_default_urls",
    "resolve_effective_index",
    "set_default_index",
    "system_uv_config_paths",
    "user_uv_config_path",
]


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


ReplaceFunction = Callable[[Path, Path], object]


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


class UvBackend:
    """`Backend` protocol implementation for uv (see `mirr.backends.base.Backend`)."""

    tool = "uv"
    SUPPORTED_VERBS = SUPPORTED_VERBS

    def locate_targets(self, *, local: bool, start: Path) -> LocalTarget:
        if local:
            return find_local_target(start)
        path = user_uv_config_path()
        return LocalTarget(path=path, kind="uv", exists=path.exists())

    def resolve_effective(self, *, start: Path) -> EffectiveIndex:
        return resolve_effective_index(start=start)

    def apply_default(
        self, target: LocalTarget, url: str, *, index_name: Optional[str] = None
    ) -> None:
        set_default_index(target, url, index_name=index_name)

    def build_probe_request(self, index: Index) -> ProbeSpec:
        return ProbeSpec(url=simple_repository_probe_url(index.url))

    def managed_urls(self, *, start: Path) -> set[str]:
        return managed_default_urls(start=start)

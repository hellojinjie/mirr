"""Index catalog management."""

from __future__ import annotations

import os
import re
import sys
import tempfile
from collections.abc import Collection, Mapping
from dataclasses import dataclass
from pathlib import Path
from types import MappingProxyType
from typing import Optional
from urllib.parse import SplitResult, urlsplit, urlunsplit

import tomlkit
from tomlkit.exceptions import TOMLKitError


class CatalogError(ValueError):
    """Raised when a catalog operation is invalid."""


@dataclass(frozen=True)
class Index:
    name: str
    url: str
    home: Optional[str] = None
    builtin: bool = False


def _builtin(name: str, url: str, home: str) -> Index:
    return Index(name=name, url=url, home=home, builtin=True)


BUILTIN_INDEXES: Mapping[str, Index] = MappingProxyType(
    {
        "pypi": _builtin("pypi", "https://pypi.org/simple", "https://pypi.org"),
        "tsinghua": _builtin(
            "tsinghua",
            "https://pypi.tuna.tsinghua.edu.cn/simple",
            "https://mirrors.tuna.tsinghua.edu.cn/help/pypi/",
        ),
        "aliyun": _builtin(
            "aliyun",
            "https://mirrors.aliyun.com/pypi/simple",
            "https://developer.aliyun.com/mirror/pypi",
        ),
        "tencent": _builtin(
            "tencent",
            "https://mirrors.cloud.tencent.com/pypi/simple",
            "https://mirrors.cloud.tencent.com/",
        ),
        "huawei": _builtin(
            "huawei",
            "https://repo.huaweicloud.com/repository/pypi/simple",
            "https://mirrors.huaweicloud.com/",
        ),
        "ustc": _builtin(
            "ustc",
            "https://mirrors.ustc.edu.cn/pypi/simple",
            "https://mirrors.ustc.edu.cn/help/pypi.html",
        ),
    }
)

_NAME_PATTERN = re.compile(r"[A-Za-z0-9][A-Za-z0-9._-]*\Z")


def default_catalog_path() -> Path:
    """Return the platform-appropriate mirr catalog path."""

    if sys.platform == "win32":
        base = Path(os.environ.get("APPDATA", Path.home() / "AppData" / "Roaming"))
    else:
        base = Path(os.environ.get("XDG_CONFIG_HOME", Path.home() / ".config"))
    return base / "mirr" / "config.toml"


def normalize_url(url: str) -> str:
    """Normalize a URL for identity comparisons without changing stored values."""

    parts = urlsplit(url)
    return urlunsplit(
        SplitResult(
            parts.scheme.lower(),
            parts.netloc.lower(),
            parts.path.rstrip("/") or "/",
            parts.query,
            parts.fragment,
        )
    )


def _validate_name(name: str) -> None:
    if not _NAME_PATTERN.fullmatch(name):
        raise CatalogError("invalid index name; use letters, numbers, dot, dash, or underscore")


def _validate_url(url: str, *, label: str = "index URL") -> None:
    parts = urlsplit(url)
    if parts.scheme not in {"http", "https"}:
        raise CatalogError(f"{label} must use http or https")
    if not parts.hostname:
        raise CatalogError(f"{label} must include a host")
    try:
        _ = parts.port
    except ValueError as exc:
        raise CatalogError(f"{label} has an invalid port") from exc
    if parts.username is not None or parts.password is not None:
        raise CatalogError(f"{label} must not contain credentials; use uv authentication")


class CatalogStore:
    """Load and persist custom entries alongside immutable built-ins."""

    def __init__(self, path: Optional[Path] = None) -> None:
        self.path = Path(path) if path is not None else default_catalog_path()

    def entries(self) -> dict[str, Index]:
        entries = dict(BUILTIN_INDEXES)
        entries.update(self._load_custom())
        return entries

    def get(self, name: str) -> Index:
        try:
            return self.entries()[name]
        except KeyError as exc:
            raise CatalogError(f"unknown index: {name}") from exc

    def add(self, name: str, url: str, home: Optional[str] = None) -> None:
        _validate_name(name)
        _validate_url(url)
        if home is not None:
            _validate_url(home, label="homepage URL")
        custom = self._load_custom()
        if name in BUILTIN_INDEXES or name in custom:
            raise CatalogError(f"index already exists: {name}")
        custom[name] = Index(name=name, url=url, home=home)
        self._write_custom(custom)

    def delete(self, name: str, active_urls: Collection[str] = ()) -> None:
        if name in BUILTIN_INDEXES:
            raise CatalogError(f"cannot delete built-in index: {name}")
        custom = self._load_custom()
        if name not in custom:
            raise CatalogError(f"unknown index: {name}")
        active = {normalize_url(url) for url in active_urls}
        if normalize_url(custom[name].url) in active:
            raise CatalogError(f"index is currently selected: {name}; select another index first")
        del custom[name]
        self._write_custom(custom)

    def rename(self, name: str, new_name: str) -> None:
        if name in BUILTIN_INDEXES:
            raise CatalogError(f"cannot rename built-in index: {name}")
        _validate_name(new_name)
        custom = self._load_custom()
        if name not in custom:
            raise CatalogError(f"unknown index: {name}")
        if new_name in BUILTIN_INDEXES or new_name in custom:
            raise CatalogError(f"index already exists: {new_name}")
        old = custom.pop(name)
        custom[new_name] = Index(name=new_name, url=old.url, home=old.home)
        self._write_custom(custom)

    def _load_custom(self) -> dict[str, Index]:
        if not self.path.exists():
            return {}
        try:
            document = tomlkit.parse(self.path.read_text(encoding="utf-8"))
        except (OSError, TOMLKitError) as exc:
            raise CatalogError(f"cannot read catalog {self.path}: {exc}") from exc

        registries = document.get("registries", {})
        if not isinstance(registries, dict):
            raise CatalogError("catalog registries must be a table")

        custom: dict[str, Index] = {}
        for name, raw in registries.items():
            if not isinstance(raw, dict):
                raise CatalogError(f"catalog entry must be a table: {name}")
            try:
                url = str(raw["url"])
            except KeyError as exc:
                raise CatalogError(f"catalog entry has no URL: {name}") from exc
            home_value = raw.get("home")
            home = str(home_value) if home_value is not None else None
            _validate_name(name)
            _validate_url(url)
            if home is not None:
                _validate_url(home, label="homepage URL")
            if name in BUILTIN_INDEXES:
                raise CatalogError(f"custom index shadows built-in index: {name}")
            custom[name] = Index(name=name, url=url, home=home)
        return custom

    def _write_custom(self, custom: Mapping[str, Index]) -> None:
        document = tomlkit.document()
        registries = tomlkit.table()
        for name, index in custom.items():
            entry = tomlkit.table()
            entry.add("url", index.url)
            if index.home is not None:
                entry.add("home", index.home)
            registries.add(name, entry)
        document.add("registries", registries)
        rendered = tomlkit.dumps(document)
        tomlkit.parse(rendered)

        self.path.parent.mkdir(parents=True, exist_ok=True)
        existing_mode = self.path.stat().st_mode if self.path.exists() else None
        temporary: Optional[Path] = None
        try:
            with tempfile.NamedTemporaryFile(
                mode="w",
                encoding="utf-8",
                dir=self.path.parent,
                prefix=f".{self.path.name}.",
                delete=False,
            ) as handle:
                temporary = Path(handle.name)
                handle.write(rendered)
                handle.flush()
                os.fsync(handle.fileno())
            if existing_mode is not None:
                os.chmod(temporary, existing_mode)
            os.replace(temporary, self.path)
            temporary = None
        except OSError as exc:
            raise CatalogError(f"cannot write catalog {self.path}: {exc}") from exc
        finally:
            if temporary is not None:
                try:
                    temporary.unlink()
                except FileNotFoundError:
                    pass

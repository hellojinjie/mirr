from __future__ import annotations

from pathlib import Path

import pytest

from uim.catalog import BUILTIN_INDEXES, CatalogError, CatalogStore

EXPECTED_BUILTINS = {
    "pypi": "https://pypi.org/simple",
    "tsinghua": "https://pypi.tuna.tsinghua.edu.cn/simple",
    "aliyun": "https://mirrors.aliyun.com/pypi/simple",
    "tencent": "https://mirrors.cloud.tencent.com/pypi/simple",
    "huawei": "https://repo.huaweicloud.com/repository/pypi/simple",
    "ustc": "https://mirrors.ustc.edu.cn/pypi/simple",
}


def test_builtin_catalog_has_supported_https_simple_indexes() -> None:
    assert {name: index.url for name, index in BUILTIN_INDEXES.items()} == EXPECTED_BUILTINS
    assert all(index.builtin for index in BUILTIN_INDEXES.values())
    assert all(index.home.startswith("https://") for index in BUILTIN_INDEXES.values())


def test_custom_catalog_round_trip_preserves_optional_homepage(tmp_path: Path) -> None:
    path = tmp_path / "uim" / "config.toml"
    store = CatalogStore(path)

    store.add(
        "company",
        "https://packages.example.com/simple",
        "https://packages.example.com",
    )

    reloaded = CatalogStore(path)
    assert reloaded.get("company").url == "https://packages.example.com/simple"
    assert reloaded.get("company").home == "https://packages.example.com"
    assert not reloaded.get("company").builtin


def test_custom_catalog_round_trip_without_homepage(tmp_path: Path) -> None:
    store = CatalogStore(tmp_path / "config.toml")

    store.add("company", "https://packages.example.com/simple")

    assert CatalogStore(store.path).get("company").home is None


@pytest.mark.parametrize(
    ("name", "url", "message"),
    [
        ("bad name", "https://packages.example.com/simple", "invalid index name"),
        ("company", "ftp://packages.example.com/simple", "http or https"),
        ("company", "https:///simple", "host"),
        ("company", "https://user:secret@packages.example.com/simple", "credentials"),
    ],
)
def test_add_rejects_invalid_entries_without_creating_config(
    tmp_path: Path,
    name: str,
    url: str,
    message: str,
) -> None:
    path = tmp_path / "config.toml"
    store = CatalogStore(path)

    with pytest.raises(CatalogError, match=message):
        store.add(name, url)

    assert not path.exists()


def test_custom_name_cannot_shadow_builtin_or_existing_entry(tmp_path: Path) -> None:
    store = CatalogStore(tmp_path / "config.toml")
    store.add("company", "https://packages.example.com/simple")
    original = store.path.read_bytes()

    with pytest.raises(CatalogError, match="already exists"):
        store.add("pypi", "https://other.example.com/simple")
    with pytest.raises(CatalogError, match="already exists"):
        store.add("company", "https://other.example.com/simple")

    assert store.path.read_bytes() == original


def test_builtin_entries_cannot_be_deleted_or_renamed(tmp_path: Path) -> None:
    store = CatalogStore(tmp_path / "config.toml")

    with pytest.raises(CatalogError, match="built-in"):
        store.delete("pypi")
    with pytest.raises(CatalogError, match="built-in"):
        store.rename("pypi", "official")


def test_delete_and_rename_custom_entries(tmp_path: Path) -> None:
    store = CatalogStore(tmp_path / "config.toml")
    store.add("old", "https://old.example.com/simple")

    store.rename("old", "new")
    assert store.get("new").url == "https://old.example.com/simple"
    with pytest.raises(CatalogError, match="unknown"):
        store.get("old")

    store.delete("new")
    with pytest.raises(CatalogError, match="unknown"):
        store.get("new")


def test_active_custom_entry_cannot_be_deleted(tmp_path: Path) -> None:
    store = CatalogStore(tmp_path / "config.toml")
    store.add("company", "https://packages.example.com/simple")
    original = store.path.read_bytes()

    with pytest.raises(CatalogError, match="currently selected"):
        store.delete("company", active_urls={"https://packages.example.com/simple/"})

    assert store.path.read_bytes() == original


def test_url_credentials_are_redacted_from_errors(tmp_path: Path) -> None:
    store = CatalogStore(tmp_path / "config.toml")

    with pytest.raises(CatalogError) as error:
        store.add("company", "https://alice:super-secret@packages.example.com/simple")

    assert "alice" not in str(error.value)
    assert "super-secret" not in str(error.value)

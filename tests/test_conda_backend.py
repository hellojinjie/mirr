from __future__ import annotations

from pathlib import Path

import pytest

from mirr.backends.base import ConfigEditorError
from mirr.backends.conda import CondaBackend, channel_repodata_url
from mirr.catalog import BUILTIN_CONDA_INDEXES, Index


def test_builtin_conda_catalog_has_expected_channels() -> None:
    assert {name: index.url for name, index in BUILTIN_CONDA_INDEXES.items()} == {
        "defaults": "https://repo.anaconda.com/pkgs/main",
        "tsinghua": "https://mirrors.tuna.tsinghua.edu.cn/anaconda/pkgs/main",
        "ustc": "https://mirrors.ustc.edu.cn/anaconda/pkgs/main",
        "huawei": "https://mirrors.huaweicloud.com/repository/conda/pkgs/main",
    }
    assert all(index.builtin for index in BUILTIN_CONDA_INDEXES.values())


def test_channel_repodata_url_appends_noarch_repodata() -> None:
    assert (
        channel_repodata_url("https://repo.anaconda.com/pkgs/main")
        == "https://repo.anaconda.com/pkgs/main/noarch/repodata.json"
    )
    assert (
        channel_repodata_url("https://repo.anaconda.com/pkgs/main/")
        == "https://repo.anaconda.com/pkgs/main/noarch/repodata.json"
    )


def test_conda_backend_supports_only_ls_and_test() -> None:
    assert CondaBackend.SUPPORTED_VERBS == frozenset({"ls", "test"})


def test_conda_backend_build_probe_request_targets_repodata() -> None:
    backend = CondaBackend()
    index = Index("tsinghua", "https://mirrors.tuna.tsinghua.edu.cn/anaconda/pkgs/main")

    spec = backend.build_probe_request(index)

    assert spec.url == "https://mirrors.tuna.tsinghua.edu.cn/anaconda/pkgs/main/noarch/repodata.json"


def test_conda_backend_write_operations_raise_not_supported() -> None:
    backend = CondaBackend()

    with pytest.raises(ConfigEditorError, match="not supported"):
        backend.locate_targets(local=False, start=Path("."))
    with pytest.raises(ConfigEditorError, match="not supported"):
        backend.resolve_effective(start=Path("."))
    with pytest.raises(ConfigEditorError, match="not supported"):
        # apply_default raises before it ever touches `target`.
        backend.apply_default(None, "https://example.com")


def test_conda_backend_managed_urls_is_always_empty() -> None:
    assert CondaBackend().managed_urls(start=Path(".")) == set()

from __future__ import annotations

import stat
from pathlib import Path
from typing import Optional

import pytest
import tomlkit

from mirr.config import LocalTarget
from mirr.editor import ConfigEditorError, set_default_index


def test_uv_toml_switch_preserves_comments_and_supplemental_indexes(tmp_path: Path) -> None:
    path = tmp_path / "uv.toml"
    path.write_text(
        "# keep this comment\n"
        'index-url = "https://old.example/simple"\n'
        "preview = true\n\n"
        "[[index]]\n"
        'name = "pytorch"\n'
        'url = "https://download.pytorch.org/whl/cpu"\n'
        "explicit = true\n",
        encoding="utf-8",
    )

    set_default_index(LocalTarget(path, "uv", True), "https://pypi.org/simple")

    content = path.read_text(encoding="utf-8")
    document = tomlkit.parse(content)
    assert "# keep this comment" in content
    assert "index-url" not in document
    assert document["default-index"] == "https://pypi.org/simple"
    assert document["preview"] is True
    assert document["index"][0]["name"] == "pytorch"
    assert document["index"][0]["explicit"] is True


def test_pyproject_switch_preserves_project_and_updates_tool_uv(tmp_path: Path) -> None:
    path = tmp_path / "pyproject.toml"
    path.write_text(
        '# project comment\n[project]\nname = "demo"\n\n[tool.uv]\npreview = true\n',
        encoding="utf-8",
    )

    set_default_index(LocalTarget(path, "pyproject", True), "https://pypi.org/simple")

    content = path.read_text(encoding="utf-8")
    document = tomlkit.parse(content)
    assert "# project comment" in content
    assert document["project"]["name"] == "demo"
    assert document["tool"]["uv"]["preview"] is True
    assert document["tool"]["uv"]["default-index"] == "https://pypi.org/simple"


def test_simple_structured_default_is_replaced_by_scalar_default(tmp_path: Path) -> None:
    path = tmp_path / "uv.toml"
    path.write_text(
        '[[index]]\nurl = "https://old.example/simple"\ndefault = true\n',
        encoding="utf-8",
    )

    set_default_index(LocalTarget(path, "uv", True), "https://new.example/simple")

    document = tomlkit.parse(path.read_text(encoding="utf-8"))
    assert document["default-index"] == "https://new.example/simple"
    assert not document.get("index")


def test_structured_default_with_extra_semantics_is_rejected_unchanged(tmp_path: Path) -> None:
    path = tmp_path / "uv.toml"
    path.write_text(
        "[[index]]\n"
        'name = "company"\n'
        'url = "https://company.example/simple"\n'
        "default = true\n"
        'authenticate = "always"\n',
        encoding="utf-8",
    )
    original = path.read_bytes()

    with pytest.raises(ConfigEditorError, match="structured default"):
        set_default_index(LocalTarget(path, "uv", True), "https://pypi.org/simple")

    assert path.read_bytes() == original


def test_malformed_configuration_is_rejected_unchanged(tmp_path: Path) -> None:
    path = tmp_path / "uv.toml"
    path.write_text('default-index = "unterminated\n', encoding="utf-8")
    original = path.read_bytes()

    with pytest.raises(ConfigEditorError, match="cannot parse"):
        set_default_index(LocalTarget(path, "uv", True), "https://pypi.org/simple")

    assert path.read_bytes() == original


def test_failed_atomic_replace_leaves_original_and_removes_temporary_file(tmp_path: Path) -> None:
    path = tmp_path / "uv.toml"
    path.write_text('default-index = "https://old.example/simple"\n', encoding="utf-8")
    original = path.read_bytes()
    observed_source: Optional[Path] = None

    def fail_replace(source: Path, destination: Path) -> None:
        nonlocal observed_source
        observed_source = Path(source)
        assert observed_source.parent == destination.parent
        raise OSError("injected replace failure")

    with pytest.raises(ConfigEditorError, match="injected replace failure"):
        set_default_index(
            LocalTarget(path, "uv", True),
            "https://new.example/simple",
            replace=fail_replace,
        )

    assert path.read_bytes() == original
    assert observed_source is not None
    assert not observed_source.exists()


def test_switch_preserves_existing_file_permissions(tmp_path: Path) -> None:
    path = tmp_path / "uv.toml"
    path.write_text('default-index = "https://old.example/simple"\n', encoding="utf-8")
    path.chmod(0o640)

    set_default_index(LocalTarget(path, "uv", True), "https://new.example/simple")

    assert stat.S_IMODE(path.stat().st_mode) == 0o640


def test_new_local_uv_toml_is_created_with_selected_default(tmp_path: Path) -> None:
    path = tmp_path / "uv.toml"

    set_default_index(LocalTarget(path, "new", False), "https://pypi.org/simple")

    assert tomlkit.parse(path.read_text(encoding="utf-8"))["default-index"] == (
        "https://pypi.org/simple"
    )

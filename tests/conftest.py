from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path

import pytest

from mirr.backends.uv import user_uv_config_path
from mirr.catalog import default_catalog_path


@dataclass(frozen=True)
class IsolatedEnvironment:
    root: Path
    home: Path
    xdg_config: Path
    appdata: Path
    localappdata: Path
    programdata: Path
    project: Path
    user_uv_config: Path
    catalog_path: Path


@pytest.fixture
def isolated_env(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> IsolatedEnvironment:
    home = tmp_path / "home"
    xdg_config = tmp_path / "xdg"
    appdata = tmp_path / "appdata"
    localappdata = tmp_path / "localappdata"
    programdata = tmp_path / "programdata"
    project = tmp_path / "project"
    for path in (home, xdg_config, appdata, localappdata, programdata, project):
        path.mkdir()

    monkeypatch.setenv("HOME", str(home))
    monkeypatch.setenv("XDG_CONFIG_HOME", str(xdg_config))
    monkeypatch.setenv("APPDATA", str(appdata))
    monkeypatch.setenv("LOCALAPPDATA", str(localappdata))
    monkeypatch.setenv("PROGRAMDATA", str(programdata))
    for variable in ("UV_DEFAULT_INDEX", "UV_INDEX_URL"):
        monkeypatch.delenv(variable, raising=False)
    monkeypatch.chdir(project)

    return IsolatedEnvironment(
        root=tmp_path,
        home=home,
        xdg_config=xdg_config,
        appdata=appdata,
        localappdata=localappdata,
        programdata=programdata,
        project=project,
        user_uv_config=user_uv_config_path(),
        catalog_path=default_catalog_path(),
    )


@pytest.fixture
def malformed_uv_config(isolated_env: IsolatedEnvironment) -> Path:
    path = isolated_env.user_uv_config
    path.parent.mkdir(parents=True)
    path.write_text('default-index = "unterminated\n', encoding="utf-8")
    return path

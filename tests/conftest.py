from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path

import pytest


@dataclass(frozen=True)
class IsolatedEnvironment:
    root: Path
    home: Path
    xdg_config: Path
    appdata: Path
    programdata: Path
    project: Path


@pytest.fixture
def isolated_env(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> IsolatedEnvironment:
    home = tmp_path / "home"
    xdg_config = tmp_path / "xdg"
    appdata = tmp_path / "appdata"
    programdata = tmp_path / "programdata"
    project = tmp_path / "project"
    for path in (home, xdg_config, appdata, programdata, project):
        path.mkdir()

    monkeypatch.setenv("HOME", str(home))
    monkeypatch.setenv("XDG_CONFIG_HOME", str(xdg_config))
    monkeypatch.setenv("APPDATA", str(appdata))
    monkeypatch.setenv("PROGRAMDATA", str(programdata))
    for variable in ("UV_DEFAULT_INDEX", "UV_INDEX_URL"):
        monkeypatch.delenv(variable, raising=False)
    monkeypatch.chdir(project)

    return IsolatedEnvironment(
        root=tmp_path,
        home=home,
        xdg_config=xdg_config,
        appdata=appdata,
        programdata=programdata,
        project=project,
    )


@pytest.fixture
def malformed_uv_config(isolated_env: IsolatedEnvironment) -> Path:
    path = isolated_env.xdg_config / "uv" / "uv.toml"
    path.parent.mkdir(parents=True)
    path.write_text('default-index = "unterminated\n', encoding="utf-8")
    return path

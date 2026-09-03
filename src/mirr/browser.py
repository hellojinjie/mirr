"""Safe browser integration for index homepages."""

from __future__ import annotations

import shutil
import subprocess
import webbrowser
from collections.abc import Sequence
from pathlib import Path
from typing import Callable, Optional

from uim.catalog import Index


class BrowserError(RuntimeError):
    """Raised when an index homepage cannot be opened."""


def open_index_home(
    index: Index,
    browser: Optional[str] = None,
    *,
    default_open: Callable[[str], bool] = webbrowser.open,
    which: Callable[[str], Optional[str]] = shutil.which,
    launch: Callable[[Sequence[str]], object] = subprocess.Popen,
) -> None:
    if index.home is None:
        raise BrowserError(f"index has no homepage: {index.name}")
    if browser is None:
        try:
            opened = default_open(index.home)
        except (OSError, webbrowser.Error) as exc:
            raise BrowserError(f"could not open homepage for {index.name}: {exc}") from exc
        if not opened:
            raise BrowserError(f"could not open homepage for {index.name}")
        return

    requested = Path(browser).expanduser()
    executable = str(requested) if requested.is_file() else which(browser)
    if executable is None:
        raise BrowserError(f"cannot find browser: {browser}")
    try:
        launch([executable, index.home])
    except OSError as exc:
        raise BrowserError(f"could not open homepage for {index.name}: {exc}") from exc

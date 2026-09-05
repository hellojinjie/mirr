"""Concurrent package-index reachability probes."""

from __future__ import annotations

import re
import time
from collections.abc import Iterable
from concurrent.futures import ThreadPoolExecutor
from dataclasses import dataclass
from typing import Callable, Optional
from urllib.error import HTTPError
from urllib.parse import SplitResult, urlsplit, urlunsplit
from urllib.request import Request, urlopen

from mirr import __version__
from mirr.catalog import Index


@dataclass(frozen=True)
class ProbeResult:
    name: str
    url: str
    ok: bool
    latency_ms: Optional[float]
    error: Optional[str]


def _redact_error(message: str) -> str:
    def replace(match: re.Match[str]) -> str:
        raw = match.group(0)
        parts = urlsplit(raw)
        hostname = parts.hostname or "redacted-host"
        netloc = hostname
        if parts.port is not None:
            netloc = f"{netloc}:{parts.port}"
        return urlunsplit(
            SplitResult(parts.scheme, netloc, parts.path, parts.query, parts.fragment)
        )

    return re.sub(r"https?://[^\s]+", replace, message)


def simple_repository_probe_url(index_url: str) -> str:
    """Lightweight PEP 503 Simple Repository project endpoint to probe.

    Shared by the uv and pip backends, which both speak this protocol; other
    backends supply their own `build_probe_url` to `probe_index`/`probe_indexes`.
    """

    parts = urlsplit(index_url)
    path = f"{parts.path.rstrip('/')}/pip/"
    return urlunsplit(SplitResult(parts.scheme, parts.netloc, path, parts.query, parts.fragment))


def _request(url: str, method: str) -> Request:
    headers = {
        "Accept": "text/html, application/vnd.pypi.simple.v1+json",
        "User-Agent": f"mirr/{__version__}",
    }
    if method == "GET":
        headers["Range"] = "bytes=0-0"
    return Request(url, headers=headers, method=method)


def _acceptable_status(response: object) -> bool:
    status = getattr(response, "status", 200)
    if status in {405, 501}:
        return False
    if not 200 <= status < 400:
        raise OSError(f"unexpected HTTP status {status}")
    return True


def probe_index(
    index: Index,
    timeout: float = 5.0,
    *,
    build_probe_url: Callable[[str], str] = simple_repository_probe_url,
    opener: Callable[..., object] = urlopen,
    clock: Callable[[], float] = time.monotonic,
) -> ProbeResult:
    probe_url = build_probe_url(index.url)
    started = clock()
    try:
        use_get = False
        try:
            with opener(_request(probe_url, "HEAD"), timeout=timeout) as response:
                use_get = not _acceptable_status(response)
        except HTTPError as exc:
            if exc.code not in {405, 501}:
                raise
            use_get = True

        if use_get:
            with opener(_request(probe_url, "GET"), timeout=timeout) as response:
                _acceptable_status(response)
                response.read(1)

        elapsed = round((clock() - started) * 1000, 3)
        return ProbeResult(index.name, index.url, True, elapsed, None)
    except (OSError, ValueError) as exc:
        return ProbeResult(index.name, index.url, False, None, _redact_error(str(exc)))


ProbeFunction = Callable[[Index, float], ProbeResult]


def probe_indexes(
    indexes: Iterable[Index],
    *,
    timeout: float = 5.0,
    max_workers: int = 4,
    probe: ProbeFunction = probe_index,
) -> list[ProbeResult]:
    items = list(indexes)
    if not items:
        return []
    workers = max(1, min(max_workers, len(items)))
    with ThreadPoolExecutor(max_workers=workers) as executor:
        return list(executor.map(lambda index: probe(index, timeout), items))

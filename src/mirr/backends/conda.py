"""conda backend: reachability-only support for conda channel mirrors.

conda's channel configuration is an ordered list, not a single default like
uv/pip/npm's `index-url`/`registry` - there's no single "effective channel"
to resolve. This phase deliberately ships only `ls` (built-ins, no "current"
marker) and `test`; `locate_targets`/`resolve_effective`/`apply_default`
exist only for structural `Backend` conformance and are never reached by the
CLI, since every write verb is routed to the shared "not supported yet" stub
before it would call into them.
"""

from __future__ import annotations

from pathlib import Path
from typing import Optional

from mirr.backends.base import ConfigEditorError, EffectiveIndex, LocalTarget, ProbeSpec
from mirr.catalog import Index

SUPPORTED_VERBS = frozenset({"ls", "test"})

_UNSUPPORTED_MESSAGE = (
    "conda channel switching is not supported yet; mirr conda currently only "
    "supports 'ls' and 'test'"
)


def channel_repodata_url(channel_url: str) -> str:
    """Lightweight `noarch/repodata.json` endpoint used to probe a channel."""

    return channel_url.rstrip("/") + "/noarch/repodata.json"


class CondaBackend:
    """`Backend` protocol implementation for conda (see `mirr.backends.base.Backend`).

    Only `build_probe_request` is ever called in this phase; the rest raise
    defensively and exist for structural conformance with `Backend`.
    """

    tool = "conda"
    SUPPORTED_VERBS = SUPPORTED_VERBS

    def locate_targets(self, *, local: bool, start: Path) -> LocalTarget:
        raise ConfigEditorError(_UNSUPPORTED_MESSAGE)

    def resolve_effective(self, *, start: Path) -> EffectiveIndex:
        raise ConfigEditorError(_UNSUPPORTED_MESSAGE)

    def apply_default(
        self, target: LocalTarget, url: str, *, index_name: Optional[str] = None
    ) -> None:
        raise ConfigEditorError(_UNSUPPORTED_MESSAGE)

    def build_probe_request(self, index: Index) -> ProbeSpec:
        return ProbeSpec(url=channel_repodata_url(index.url))

    def managed_urls(self, *, start: Path) -> set[str]:
        return set()

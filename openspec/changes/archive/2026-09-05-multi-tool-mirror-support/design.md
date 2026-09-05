## Context

See proposal.md - Why. Today all four `mirr` modules (`catalog.py`, `config.py`, `editor.py`, `probe.py`) hard-code uv's TOML config format, its `uv.toml`/`pyproject.toml` project-file discovery, its `[[index]] default = true` write semantics, and a probe path builder (`_project_url`) that appends `/pip/<pkg>/` — a Simple Repository convention shared by uv and pip but meaningless for npm or conda. `cli.py` is a flat `click.Group` with no notion of "which tool."

## Goals / Non-Goals

**Goals:**
- Introduce a shared backend protocol so uv/pip/npm/conda each supply only what differs (config locations, effective-value resolution, atomic write, probe URL construction).
- Keep every existing no-prefix command byte-for-byte identical in behavior (see `mirr-cli-dispatch` spec).
- Ship pip and npm with full read/write parity to uv's current feature set.
- Ship conda read-only (`ls`/`test`) this round; defer channel-list write semantics.

**Non-Goals:**
- Designing conda's `use`/`add`/`del`/`rename` semantics (ordered channel list vs single default) — explicitly deferred to a future change.
- Parsing or writing `.condarc` in any form — phase 1 needs neither (see Decisions).
- A generic plugin system for third-party/out-of-tree backends — the four backends are fixed, in-tree modules.
- Changing uv's on-disk behavior or file formats.

## Decisions

### 1. Backend protocol shape
Each backend module exposes the same small surface, mirroring what `config.py`/`editor.py`/`probe.py` already do for uv:
- `locate_targets(*, local: bool, start: Path) -> LocalTarget` (or venv-equivalent for pip) — where a "use" would write.
- `resolve_effective(*, start: Path) -> EffectiveIndex` — env var / scope precedence lookup, tool-specific.
- `apply_default(target, url, *, index_name) -> None` — atomic write, tool-specific format.
- `build_probe_request(index: Index) -> ProbeSpec` — the URL/method the shared `probe.py` HEAD/GET/Range loop should hit.
- `SUPPORTED_VERBS: frozenset[str]` — what `mirr-cli-dispatch` is allowed to route to this backend (`{"ls", "test"}` for conda; the full set for uv/pip/npm).

`catalog.py`'s `CatalogStore`, `Index`, `normalize_url`, and validation helpers stay tool-agnostic and are reused unchanged, parameterized by which per-tool file to read/write (see Decision 3).

**Alternative considered**: one big `if tool == ...` branch inside the existing modules. Rejected — it would keep growing every uv-specific assumption (TOML parsing, `/pip/` probe suffix) as implicit defaults that new tools have to fight, instead of making each backend responsible for its own semantics.

### 2. CLI routing
`cli.py` becomes a top-level `click.Group` with four sub-groups (`uv`, `pip`, `npm`, `conda`), each a `click.Group` whose commands call straight into that tool's backend + the shared `catalog`/`probe` plumbing. The existing no-prefix commands (`ls`, `current`, `use`, ...) become thin wrappers that invoke the `uv` sub-group's command callback directly (in-process function call, not a subprocess re-invocation) so behavior, error classes, and exit codes stay identical by construction — verified by a regression test asserting alias output equals `mirr uv <verb>` output for the same inputs.

A sub-group only registers the commands in its backend's `SUPPORTED_VERBS`, so `mirr conda --help` naturally lists just `ls`/`test`. For the omitted verbs (`use`/`add`/`del`/`rename`/`current` on conda), a lightweight stub command is still registered so users get the "not supported yet" message from the `mirr-cli-dispatch` spec instead of Click's generic "no such command" error.

### 3. Catalog file split
`CatalogStore` gains a required `tool: str` used only to pick the default path (`default_catalog_path(tool=...)` → `~/.config/mirr/{tool}.toml`) and the right built-in table (`BUILTIN_INDEXES` becomes `BUILTIN_INDEXES_BY_TOOL[tool]`). The on-disk **format** of every catalog file stays TOML via `tomlkit` regardless of which real tool it targets — this is mirr's own bookkeeping format, independent of pip's INI or npm's `.npmrc` syntax. The existing `~/.config/mirr/config.toml` is reused verbatim as `uv.toml` (same path resolution `default_catalog_path(tool="uv")` must resolve to the historical path) — no migration step, no schema version bump.

### 4. Target-file editors: hand-rolled line patches, not generic parsers
uv's `editor.py` gets away with full-fidelity comment/format preservation because `tomlkit` is a round-trip TOML library. Neither pip's `pip.conf` (INI) nor npm's `.npmrc` (flat `key = value` lines, no real section nesting in practice) has an equivalent round-trip library in the stdlib — `configparser` reads structure but silently drops comments on write.

Decision: for both pip and npm, write a minimal line-oriented patcher analogous in spirit to `_apply_structured_default`: read the file as lines, find the line setting the managed key (`index-url` under `[global]` for pip; `registry` for npm) within the right section/scope, replace that line in place, or append a new line/section if absent. Every other line is copied through untouched, which trivially satisfies the "preserve unrelated settings and comments" requirement in both new specs without needing a real parser. This is more code than reusing `configparser`, but avoids silently regressing the comment-preservation guarantee that `uv-index-management` established as a user-facing bar.

**Alternative considered**: `configparser` for pip. Rejected — comment loss is a regression against the pattern already shipped for uv, and pip.conf's structure is simple enough (single `[global]` section, single key) that a line patch is not meaningfully riskier than a full INI writer.

### 5. conda: no `.condarc` parsing this round
Because phase 1 only ships `ls` (lists built-ins, explicitly does not resolve "current") and `test` (probes catalog URLs directly), nothing in this change ever reads or writes `.condarc`. This resolves the proposal's open "do we need a YAML dependency" question: **no** — no YAML library is added in this change. The question re-opens only when a future change adds `use`/`current` for conda and has to decide the channel-list write semantics; that future change picks the YAML approach (dependency vs hand-rolled) then, informed by whatever ordering/dedup semantics it settles on.

### 6. Probe URL construction per backend
`probe.py`'s HEAD-then-GET-with-Range loop and error redaction stay shared and untouched. Only the URL-building step becomes backend-supplied:
- uv/pip: unchanged `{index_url}/{fixed probe project}/pip/` (already what `_project_url` does).
- npm: registry root (or a documented lightweight path if the root itself returns a large body) — exact endpoint confirmed against real mirrors during implementation, tracked as a task, not a spec-level detail.
- conda: `{channel}/noarch/repodata.json`, same HEAD-first/Range-GET-fallback strategy, never reading past the first byte on success.

### 7. Built-in catalogs per tool
- pip reuses the exact same six entries (name, URL) as uv — same Simple Repository URLs work for both.
- npm ships official `npmjs` plus commonly used domestic mirrors (npmmirror/taobao, Tencent, Huawei) — exact URLs finalized during implementation and validated live (task item), not hard-coded in the spec.
- conda ships `defaults` plus domestic conda mirrors, same "validate live" treatment - implementation confirmed Aliyun's conda mirror is no longer reachable and substituted Huawei Cloud's instead (see tasks.md 5.1).

## Risks / Trade-offs

- [pip's `--local` has no true project-file equivalent, only venv] → Mitigated by a specific, actionable error message when no venv is active (see `pip-index-management` spec's venv-level scenario), rather than silently falling back to user scope.
- [Hand-rolled line patchers for pip/npm are more code and more edge cases (e.g., key already present with unusual spacing) than a library parser] → Mitigated by scoping each patcher to exactly one managed key per file, mirroring the narrow scope `editor.py` already has for uv, plus dedicated regression tests per backend analogous to `test_regressions.py`.
- [Built-in mirror URLs for npm/conda are asserted in this design without having been probed yet] → Mitigated by treating "confirm real endpoint paths and URLs against live mirrors" as an explicit implementation task before those backends ship, not an assumption baked into the spec text.
- [Growing the CLI surface risks breaking scripts that parse existing output] → Mitigated by the alias requirement in `mirr-cli-dispatch` guaranteeing byte-identical behavior for every existing no-prefix command.

## Migration Plan

Purely additive: new sub-commands, new backend modules, new per-tool catalog files. The one existing file touched (`~/.config/mirr/config.toml`) keeps its exact path and format under its new logical name `uv.toml` — no data migration, no version bump, no user action required. Rollback is a plain revert; no persisted state becomes incompatible with the previous release either direction.

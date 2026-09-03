## Context

The repository currently contains only a Python 3.13 placeholder entry point. See `proposal.md` for motivation and `specs/uv-index-management/spec.md` for the observable behavior being introduced.

uv differs from npm's single-registry model: it discovers configuration at system, user, project, environment, and command-line levels; supports multiple named indexes; and gives `uv.toml` precedence over `[tool.uv]` in a colocated `pyproject.toml`. Newer uv versions also reject configurations containing multiple structured indexes marked as default. The implementation must therefore reproduce nrm's command ergonomics without treating uv configuration as an opaque registry string.

Python 3.9 support means the standard-library `tomllib` reader is unavailable, while preserving existing TOML comments and unknown fields is a product requirement.

## Goals / Non-Goals

**Goals:**

- Keep command names, positional arguments, common flags, output hierarchy, and interactive selection familiar to nrm users.
- Separate the reusable index catalog from the effective uv configuration.
- Make user and local configuration edits narrow, atomic, comment-preserving, and explainable.
- Resolve enough of uv's configuration precedence to make `current` and `ls` truthful in the current directory.
- Keep core behavior deterministic and testable on Linux, macOS, and Windows with Python 3.9+.

**Non-Goals:**

- Reimplement uv's resolver, credential store, or publish workflow.
- Treat uv package-specific sources as an npm scope equivalent.
- Modify system-level uv configuration.
- Automatically rewrite an unmanaged structured default index with additional semantics.
- Guarantee byte-for-byte formatting preservation outside the TOML nodes uim changes.

## Decisions

### Use a small layered Python CLI architecture

Organize the application into a CLI adapter, catalog service, effective-configuration resolver, TOML configuration editor, and endpoint probe. CLI commands orchestrate these services but do not parse or rewrite TOML directly.

This keeps filesystem and network behavior injectable for unit tests and prevents command-specific implementations from drifting. A single-file script was considered, but rejected because precedence resolution, cross-platform paths, and transactional editing are independently complex concerns.

### Expose `uim` through package metadata and support Python 3.9+

Define a console-script entry point backed by an importable package rather than the placeholder top-level `main.py`. Use a mature Python 3.9-compatible command framework with explicit command names and options; Click is preferred because its command model closely matches nrm's subcommands and does not require modern typing features.

The package version remains the single source for `uim --version`. Supporting Python earlier than 3.9 is excluded to limit compatibility branches; keeping the current 3.13 floor was rejected because it would create unnecessary adoption friction for a migration-oriented tool.

### Store built-ins in code and custom entries in uim configuration

Built-in index definitions are immutable packaged data. Persist only custom entries in a platform-appropriate per-user uim TOML file. At load time, merge custom entries after validating that their names do not shadow built-ins.

Do not persist a separate `current` value. The selected index is derived from effective uv configuration so manual edits and project overrides cannot make uim's display stale.

### Represent a simple selected mirror with uv's default-index setting

For a mirror switch, write uv's scalar `default-index` setting (`default-index` in `uv.toml`, or under `[tool.uv]` in `pyproject.toml`). This models the nrm operation directly while leaving supplemental `[[index]]` entries intact. When replacing the legacy scalar `index-url`, remove or normalize the superseded scalar so uv does not receive contradictory defaults.

An alternative was to add a named `[[index]]` entry with `default = true`. That was rejected because it can collide with existing structured defaults, creates a synthetic index name, and makes a simple URL switch interact with named-index semantics.

Before writing, detect any structured `[[index]]` entry marked as default. If it carries unmanaged semantics, fail with an actionable conflict message. A future explicit override option may migrate such entries, but the initial safe path never silently discards their attributes.

### Resolve write targets by scope and uv discovery behavior

For the default user scope, target uv's user configuration directory according to uv's XDG and Windows conventions and create the parent directory when needed.

For `--local`, walk from the current directory toward the applicable project root:

1. Use the nearest applicable existing `uv.toml`.
2. Otherwise use the nearest applicable `pyproject.toml` and edit `[tool.uv]`.
3. If neither exists, ask for confirmation in an interactive terminal before creating `uv.toml` in the current directory; require an explicit non-interactive confirmation flag for automation.

Do not create a colocated `uv.toml` merely because a `pyproject.toml` exists, since that would cause uv to ignore the file's `[tool.uv]` table.

### Preserve TOML structure and replace files atomically

Use `tomlkit` for both Python 3.9-compatible TOML parsing and comment-preserving mutation. Edit only the selected default scalar and any directly superseded legacy scalar. Validate the rendered document before writing it to a temporary file in the target directory, flush it, preserve existing permissions where applicable, and atomically replace the destination.

Malformed TOML, unsupported structure, write failure, or replacement failure aborts without intentionally modifying the original. Hand-built TOML serialization and `tomllib` plus a separate writer were rejected because they cannot meet comment preservation consistently.

### Model effective configuration as a value plus provenance

The resolver returns the effective URL together with its source: environment, local `uv.toml`, local `pyproject.toml`, user `uv.toml`, system configuration, or uv's implicit PyPI default. It normalizes URLs only for matching (for example, a trailing slash) and retains the configured URL for display and writing.

Apply documented uv precedence, including the modern default-index environment variable and supported legacy alias. Local and user TOML arrays and scalars are interpreted only as far as necessary to identify the effective default. `current --verbose` exposes provenance and shadowing, which helps explain why a global `use` can be hidden by a project or environment override.

Command-line flags passed to a later uv invocation cannot be predicted and are outside `uim current`'s definition of effective state.

### Use standard-library HTTPS probing with bounded concurrency

Never download or issue a `GET` for the configured `/simple` root index: public mirrors can expose tens of megabytes of project names there, delay generation of the listing, or rate-limit generic root requests. Derive a lightweight `pip/` project endpoint beneath the normalized Simple Repository URL and send an honest `uim/<version>` user agent.

Probe the lightweight endpoint with `HEAD` first so a successful check transfers no response body. If and only if the endpoint rejects `HEAD` with HTTP 405 or 501, retry the same endpoint with `GET`, `Range: bytes=0-0`, and a client-side read limit of one byte. Keep TLS verification enabled, follow standard-library redirects, apply a bounded timeout, and use bounded concurrent workers. Measure monotonic elapsed time across the complete attempt and report each entry independently in deterministic catalog order after all probes complete.

Using the standard library avoids a runtime HTTP dependency for a small health check. A root-index GET and download-throughput benchmarking were rejected because they impose unnecessary load and produce results dominated by project-list size, package choice, cache state, CDN behavior, and mirror synchronization rather than basic registry reachability.

### Delegate authentication and browser integration

Reject credentials embedded in catalog URLs and redact user information from errors. uim does not own secrets. A later `login` command can delegate to a compatible `uv auth login` executable after version detection.

Use the platform browser integration for `home`; if a browser argument is supplied, resolve only a named or explicit executable without invoking a shell.

## Risks / Trade-offs

- **[uv configuration semantics evolve]** -> Keep precedence and supported-key behavior isolated, test against a declared uv compatibility range, and add fixtures for legacy keys.
- **[Global switching appears ineffective inside an overridden project]** -> Report success for the written scope but also warn when a higher-precedence local or environment value remains effective.
- **[A user's structured default cannot be safely converted]** -> Refuse the write with provenance and remediation guidance; do not silently flatten it.
- **[Comment-preserving libraries still normalize touched TOML]** -> Restrict mutations to the smallest nodes and test representative formatting fixtures.
- **[Concurrent tests overload small private indexes]** -> Bound worker count, avoid root-index GET requests, and limit each fallback response to one byte with a configurable timeout.
- **[Built-in mirror endpoints change]** -> Keep them centralized, validate them in release checks, and allow a custom replacement under a different name without making built-ins mutable.
- **[Python package name and executable name availability differ]** -> Treat `uim` as the required executable; verify distribution-name availability before the first release and use `uv-index-manager` as the distribution fallback if necessary.

## Migration Plan

1. Convert the placeholder project into a package exposing the `uim` console command and lower `requires-python` to 3.9.
2. Add the catalog and read-only commands first so existing uv configuration can be inspected without mutation.
3. Add transactional user and local switching with fixture-based compatibility tests.
4. Add homepage and concurrent test commands, documentation, and cross-platform CI.
5. Release an initial pre-1.0 version; rollback consists of uninstalling uim, since uim does not need a daemon or shell hook and all uv changes remain ordinary TOML settings.

Before every configuration mutation, retain enough in-memory original content to leave the file untouched on failure. No automatic migration of user configuration occurs merely by installing or upgrading uim.

## Why

Users who already know nrm should be able to manage uv package indexes without learning a substantially different command vocabulary or manually editing TOML files. A dedicated `uim` CLI can provide that familiar workflow while respecting uv's layered, multi-index configuration model.

## What Changes

- Add an installable `uim` command that supports Python 3.9 and later.
- Provide nrm-compatible core commands for listing, inspecting, switching, adding, deleting, renaming, opening, and testing package indexes.
- Support user-level switching by default and project-level switching through `uim use --local`.
- Ship a curated catalog of common PyPI indexes while allowing users to maintain custom entries.
- Resolve and report the effective index for the current directory, including configuration overrides.
- Preserve unrelated uv configuration and reject unsafe conflicts instead of silently replacing unmanaged index settings.
- Keep authentication, publishing, npm scopes, and package-specific source binding outside the initial release.

## Capabilities

### New Capabilities

- `uv-index-management`: Manage a catalog of uv-compatible package indexes and safely inspect, switch, and test them through an nrm-shaped CLI at user and project scope.

### Modified Capabilities

None.

## Impact

- Replaces the placeholder application entry point with a packaged Python CLI exposed as `uim`.
- Changes the supported Python requirement from 3.13+ to 3.9+.
- Introduces dependencies for CLI interaction, HTTP probing, and comment-preserving TOML updates where needed.
- Reads and updates uv user configuration and project `uv.toml` or `pyproject.toml` files.
- Stores custom index catalog data in a platform-appropriate uim configuration directory.
- Requires cross-platform behavior and tests for Linux, macOS, and Windows path and configuration conventions.

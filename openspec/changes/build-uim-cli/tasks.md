## 1. Package and Test Foundation

- [x] 1.1 Convert the placeholder into a `src/uim` package, expose the `uim` console script, set `requires-python = ">=3.9"`, and verify `uv run uim --help` and `uv run uim --version` succeed.
- [x] 1.2 Add Python 3.9-compatible runtime and test dependencies for Click, platform path handling, comment-preserving TOML, and pytest, then verify `uv lock` and `uv sync` complete successfully.
- [x] 1.3 Establish unit-test fixtures for isolated home, XDG, Windows-style, project, environment, and malformed-config cases, then verify the fixture smoke tests do not access real user configuration.

## 2. Catalog Management

- [x] 2.1 Implement the immutable built-in catalog for PyPI, Tsinghua, Aliyun, Tencent, Huawei, and USTC, then verify tests assert every name, HTTPS Simple URL, and homepage.
- [x] 2.2 Implement platform-appropriate loading and atomic persistence of custom catalog entries, then verify round-trip tests preserve valid custom names, URLs, and optional homepages.
- [x] 2.3 Implement name and URL validation, built-in shadow protection, credential rejection, and error redaction, then verify negative tests leave the catalog file unchanged and expose no URL user information.
- [x] 2.4 Implement add, delete, and rename catalog operations including active-entry protection, then verify command tests cover success, duplicates, missing entries, built-in mutation, and active custom deletion.

## 3. uv Configuration Resolution

- [x] 3.1 Implement user, system, and local uv configuration path discovery for Linux, macOS, and Windows conventions, then verify table-driven path tests under mocked environments.
- [x] 3.2 Implement local target selection for existing `uv.toml`, existing `pyproject.toml`, and an unconfigured directory, then verify nearest-file and no-colocated-override cases with temporary directory trees.
- [x] 3.3 Implement effective default-index resolution with provenance across environment, project, user, system, legacy scalar, structured default, and implicit PyPI cases, then verify precedence tests match uv's documented order.
- [x] 3.4 Implement normalized URL-to-catalog matching without altering stored or displayed URLs, then verify trailing-slash equivalence and unknown-URL behavior.

## 4. Transactional Index Switching

- [x] 4.1 Implement comment-preserving `default-index` mutation for `uv.toml` and `[tool.uv]` mutation for `pyproject.toml`, including legacy scalar normalization, then verify fixture comparisons preserve unrelated settings, supplemental indexes, and comments.
- [x] 4.2 Implement detection and safe refusal of unmanaged structured default-index conflicts, then verify conflict fixtures remain byte-for-byte unchanged and return actionable errors.
- [x] 4.3 Implement same-directory temporary writes, validation, permission preservation, flush, and atomic replacement, then verify injected parse, write, and replace failures leave the original configuration usable.
- [x] 4.4 Implement global `uim use [name]` switching and interactive selection, then verify successful, unknown-name, interactive, and non-interactive command tests including warnings for higher-precedence overrides.
- [x] 4.5 Implement `uim use [name] --local` with interactive confirmation and an explicit automation confirmation option when creating a new `uv.toml`, then verify it never modifies user configuration and targets the expected project file.

## 5. Read-Only nrm-Compatible Commands

- [x] 5.1 Implement `uim current`, `--show-url`/`-u`, and verbose provenance output, then verify tests cover catalog matches, unknown URLs, project overrides, and environment overrides.
- [x] 5.2 Implement `uim ls` with nrm-familiar alignment and a single effective-selection marker, then verify output snapshots for known, unknown, and implicit PyPI selections.
- [x] 5.3 Implement `uim home <name> [browser]` through shell-free platform browser launching, then verify mocked tests cover default browser, requested browser, missing homepage, and launch failure.
- [x] 5.4 Implement bounded concurrent HTTPS reachability testing for one or all entries with deterministic output ordering, then verify mocked success, timeout, TLS, redirect, HTTP failure, latency, and no-mutation cases.
- [x] 5.5 Replace root-index probing with an identified `uim/<version>` `HEAD` request to a lightweight `pip/` project endpoint, fall back only on HTTP 405/501 to a `Range: bytes=0-0` GET that reads at most one byte, and verify tests prove no GET targets the root index while preserving timeout, TLS, redirect, redaction, latency, concurrency, and no-mutation behavior.

## 6. Integration, Compatibility, and Documentation

- [x] 6.1 Add end-to-end CLI tests covering the complete add/use/current/ls/rename/use/del lifecycle at both user and local scope, then verify the isolated test suite passes without touching the developer's real uv files.
- [x] 6.2 Add a supported-Python CI matrix starting at Python 3.9 plus operating-system coverage for Linux, macOS, and Windows, then verify the workflow configuration exercises the unit and CLI suites on each declared platform.
- [x] 6.3 Replace the placeholder README with installation, nrm-to-uim migration examples, command reference, configuration precedence, conflict recovery, security boundaries, and `--local` behavior, then verify every documented command is covered by help or an automated smoke test.
- [x] 6.4 Run formatting, linting, the full test suite, package build, and built wheel installation smoke tests, then verify the clean environment exposes a working `uim` command and no planning requirement remains untested.

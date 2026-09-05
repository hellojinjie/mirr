# `mirr`or

[简体中文](README.md) | English

`mirr` is an nrm-shaped mirror configuration tool for common package managers,
currently covering [uv](https://docs.astral.sh/uv/), pip, npm, and conda (read-only).
It keeps the commands familiar while respecting each tool's user, project, environment,
and multi-index configuration semantics.

## Installation

mirr requires Python 3.9 or later. Run it directly with [`uvx`](https://docs.astral.sh/uv/guides/tools/), no install needed:

```console
uvx mirr --version
```

Or install it as a persistent command:

```console
uv tool install mirr
mirr --version
```

From a checkout, for development:

```console
uv tool install .
mirr --version
```

## Migrating from nrm

The core workflows use the same command names:

| nrm | mirr | Purpose |
| --- | --- | --- |
| `nrm ls` | `mirr ls` | List indexes and mark the effective one |
| `nrm current -u` | `mirr current -u` | Show the effective index URL |
| `nrm use <name>` | `mirr use <name>` | Change the user-level default |
| `nrm use <name> --local` | `mirr use <name> --local` | Change the project default |
| `nrm add <name> <url> [home]` | `mirr add <name> <url> [home]` | Add a custom index |
| `nrm del <name>` | `mirr del <name>` | Delete a custom index |
| `nrm rename <name> <new-name>` | `mirr rename <name> <new-name>` | Rename a custom index |
| `nrm home <name> [browser]` | `mirr home <name> [browser]` | Open an index homepage |
| `nrm test [name]` | `mirr test [name]` | Measure endpoint latency |

Authentication, publishing, npm scopes, and package-specific uv source bindings are
not managed by the initial mirr release.

## Multi-tool support

Besides the bare historical commands (always equivalent to `mirr uv <verb>`), mirr also
supports an explicit `mirr <tool> <verb>` form:

```console
mirr uv use tsinghua      # same as mirr use tsinghua
mirr pip use tsinghua
mirr pip use tsinghua --local   # writes pip.conf in the active virtualenv
mirr npm use npmmirror
mirr npm use npmmirror --local  # writes .npmrc in the current directory
mirr conda ls
mirr conda test
```

| Tool | Supported commands | `--local` scope | Notes |
| --- | --- | --- | --- |
| `uv` | all | project `uv.toml`/`pyproject.toml` | identical to the historical behavior |
| `pip` | all | the active virtualenv | pip has no project-level config; `--local` errors without an active venv |
| `npm` | all | the current directory's `.npmrc` | scope overrides (e.g. `@corp:registry=`) are always preserved |
| `conda` | `ls`, `test` only | not applicable | channels are an ordered list, not a single default; write support is deferred, and `use`/`add`/`del`/`rename`/`current` clearly report as unsupported |

`mirr <tool> --help` only lists the commands that tool currently supports.

## Quick start

```console
$ mirr test
[uv] * pypi -------- 187 ms
[uv]   tsinghua ---- 43 ms
[uv]   aliyun ------ 96 ms
[uv]   tencent ----- 121 ms
[uv]   huawei ------ 88 ms
[uv]   ustc -------- 104 ms

$ mirr use tsinghua
[uv] SUCCESS The index has been changed to 'tsinghua'.

$ mirr current
[uv] You are using tsinghua index.
```

Every line carries a `[tool]` prefix stating which tool's mirror configuration it
affects - the bare commands and `mirr uv <verb>` are the same thing, so both show `[uv]`.

Run `mirr use` without a name in an interactive terminal to choose from the catalog.
For scripts, always provide the name explicitly.

## Commands

These commands are described in their bare, historical form (operating on uv); pip and
npm behave identically in arguments and output - swap in `mirr pip <verb>` or
`mirr npm <verb>`. The only differences are each tool's config file locations,
environment variable names, and where `--local` writes (see the table above).

### `mirr ls`

Lists built-in and custom entries. The `*` marks the index effective in the current
directory, not merely the last user-level selection.

### `mirr current`

Uses nrm's familiar sentence-shaped output. It shows the catalog name when the
effective URL is known, `--show-url` substitutes the URL, and an uncataloged URL
is followed by the `mirr add` command needed to catalog it.

```console
mirr current --show-url
mirr current -u
mirr current --verbose
```

Verbose output includes the source and configuration path where applicable.

### `mirr use [name]`

Changes uv's user-level `default-index` while preserving unrelated settings and named
supplemental indexes.

```console
mirr use pypi
mirr use tsinghua
```

If a project setting or `UV_DEFAULT_INDEX` still overrides the new user setting, mirr
writes the requested user configuration and prints a warning explaining the active
override.

### `mirr use [name] --local`

Changes only the current project:

1. Use the nearest applicable existing `uv.toml`.
2. Otherwise update `[tool.uv]` in the nearest `pyproject.toml`.
3. Otherwise create `uv.toml` in the current directory after confirmation.

Use `--yes` when a non-interactive script is allowed to create a new local `uv.toml`:

```console
mirr use aliyun --local --yes
```

mirr does not create a colocated `uv.toml` when `pyproject.toml` is available, because
uv would then ignore that file's `[tool.uv]` settings.

### Custom catalog entries

```console
mirr add company https://packages.example.com/simple https://packages.example.com
mirr rename company internal
mirr del internal
```

Built-in entries cannot be renamed or deleted. An active custom entry must be replaced
by another selection before deletion.

### Homepages and reachability

```console
mirr home pypi
mirr home pypi firefox
mirr test pypi
mirr test
mirr test --timeout 10
```

`mirr test` performs a lightweight, TLS-verified `HEAD` request against the `pip/`
project page beneath each Simple Repository endpoint; it never downloads the root index.
If a server does not support `HEAD`, mirr requests and reads at most one byte instead.
All-entry tests use bounded concurrency and print results in catalog order. As in nrm,
`*` marks the effective current index, columns are aligned, and the fastest successful
result is highlighted. This is a reachability and latency check, not a package-download
throughput benchmark.

## Configuration precedence

`mirr current` evaluates persistent and environment configuration in this order:

1. `UV_DEFAULT_INDEX` and the supported legacy `UV_INDEX_URL` alias
2. Project `uv.toml` or `[tool.uv]` in `pyproject.toml`
3. User `uv.toml`
4. System `uv.toml`
5. uv's implicit `https://pypi.org/simple` default

Command-line options passed to a later uv invocation are not predictable and therefore
are not included in `mirr current`.

User uv configuration follows uv's platform conventions, including
`~/.config/uv/uv.toml` with XDG support on Linux and macOS and
`%APPDATA%\uv\uv.toml` on Windows. Custom mirr entries use the platform's mirr user
configuration directory.

`mirr pip current` and `mirr npm current` follow the same "environment variable >
nearest scope > user > system/global" shape, just with different variable names and files:

| | Environment variable | Nearest scope | User-level file |
| --- | --- | --- | --- |
| pip | `PIP_INDEX_URL` | the active virtualenv (`$VIRTUAL_ENV/pip.conf`) | `pip.conf` (platform-specific path) |
| npm | `npm_config_registry` | the current directory's `.npmrc` | `~/.npmrc` |

Each tool's custom catalog is stored separately
(`~/.config/mirr/{uv,pip,npm,conda}.toml`; the historical `config.toml` is kept as-is as
uv's catalog file, no migration needed).

## Conflict recovery

mirr normally writes a scalar `default-index`. A simple anonymous structured default such as:

```toml
[[index]]
url = "https://old.example/simple"
default = true
```

can be replaced safely. A user-level `uv.toml` default containing only `name`, `url`, and
`default` is updated in place so `mirr use <name>` remains compatible with uv's named-index
format. Named defaults in `pyproject.toml`, duplicate target names, authentication behavior,
publish URLs, and other extra semantics are left unchanged and reported as conflicts for
manual review. mirr also refuses malformed TOML and leaves the original file unchanged when
parsing, validation, or atomic replacement fails.

## Security boundaries

- Catalog URLs containing embedded usernames, passwords, or tokens are rejected.
- mirr does not maintain a credential store or print URL credentials in errors.
- Configure private-index credentials with uv's supported authentication mechanisms.
- TLS verification remains enabled during `mirr test`.
- Supplying a browser launches an argument vector directly; mirr does not construct a
  shell command.

## Development

```console
uv sync --locked
uv run pytest
uv run ruff check .
uv build
```

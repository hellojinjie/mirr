# uim

`uim` is an nrm-shaped package index manager for [uv](https://docs.astral.sh/uv/).
It keeps the commands familiar while respecting uv's user, project, environment,
and multi-index configuration semantics.

## Installation

uim requires Python 3.9 or later. From a checkout:

```console
uv tool install .
uim --version
```

After the project is published, install it by distribution name:

```console
uv tool install uv-index-manager
```

## Migrating from nrm

The core workflows use the same command names:

| nrm | uim | Purpose |
| --- | --- | --- |
| `nrm ls` | `uim ls` | List indexes and mark the effective one |
| `nrm current -u` | `uim current -u` | Show the effective index URL |
| `nrm use <name>` | `uim use <name>` | Change the user-level default |
| `nrm use <name> --local` | `uim use <name> --local` | Change the project default |
| `nrm add <name> <url> [home]` | `uim add <name> <url> [home]` | Add a custom index |
| `nrm del <name>` | `uim del <name>` | Delete a custom index |
| `nrm rename <name> <new-name>` | `uim rename <name> <new-name>` | Rename a custom index |
| `nrm home <name> [browser]` | `uim home <name> [browser]` | Open an index homepage |
| `nrm test [name]` | `uim test [name]` | Measure endpoint latency |

Authentication, publishing, npm scopes, and package-specific uv source bindings are
not managed by the initial uim release.

## Quick start

```console
$ uim ls
* pypi     --- https://pypi.org/simple
  tsinghua --- https://pypi.tuna.tsinghua.edu.cn/simple
  aliyun   --- https://mirrors.aliyun.com/pypi/simple
  tencent  --- https://mirrors.cloud.tencent.com/pypi/simple
  huawei   --- https://repo.huaweicloud.com/repository/pypi/simple
  ustc     --- https://mirrors.ustc.edu.cn/pypi/simple

$ uim use tsinghua
SUCCESS The index has been changed to 'tsinghua'.

$ uim current
You are using tsinghua index.
```

Run `uim use` without a name in an interactive terminal to choose from the catalog.
For scripts, always provide the name explicitly.

## Commands

### `uim ls`

Lists built-in and custom entries. The `*` marks the index effective in the current
directory, not merely the last user-level selection.

### `uim current`

Uses nrm's familiar sentence-shaped output. It shows the catalog name when the
effective URL is known, `--show-url` substitutes the URL, and an uncataloged URL
is followed by the `uim add` command needed to catalog it.

```console
uim current --show-url
uim current -u
uim current --verbose
```

Verbose output includes the source and configuration path where applicable.

### `uim use [name]`

Changes uv's user-level `default-index` while preserving unrelated settings and named
supplemental indexes.

```console
uim use pypi
uim use tsinghua
```

If a project setting or `UV_DEFAULT_INDEX` still overrides the new user setting, uim
writes the requested user configuration and prints a warning explaining the active
override.

### `uim use [name] --local`

Changes only the current project:

1. Use the nearest applicable existing `uv.toml`.
2. Otherwise update `[tool.uv]` in the nearest `pyproject.toml`.
3. Otherwise create `uv.toml` in the current directory after confirmation.

Use `--yes` when a non-interactive script is allowed to create a new local `uv.toml`:

```console
uim use aliyun --local --yes
```

uim does not create a colocated `uv.toml` when `pyproject.toml` is available, because
uv would then ignore that file's `[tool.uv]` settings.

### Custom catalog entries

```console
uim add company https://packages.example.com/simple https://packages.example.com
uim rename company internal
uim del internal
```

Built-in entries cannot be renamed or deleted. An active custom entry must be replaced
by another selection before deletion.

### Homepages and reachability

```console
uim home pypi
uim home pypi firefox
uim test pypi
uim test
uim test --timeout 10
```

`uim test` performs a lightweight, TLS-verified `HEAD` request against the `pip/`
project page beneath each Simple Repository endpoint; it never downloads the root index.
If a server does not support `HEAD`, uim requests and reads at most one byte instead.
All-entry tests use bounded concurrency and print results in catalog order. As in nrm,
`*` marks the effective current index, columns are aligned, and the fastest successful
result is highlighted. This is a reachability and latency check, not a package-download
throughput benchmark.

## Configuration precedence

`uim current` evaluates persistent and environment configuration in this order:

1. `UV_DEFAULT_INDEX` and the supported legacy `UV_INDEX_URL` alias
2. Project `uv.toml` or `[tool.uv]` in `pyproject.toml`
3. User `uv.toml`
4. System `uv.toml`
5. uv's implicit `https://pypi.org/simple` default

Command-line options passed to a later uv invocation are not predictable and therefore
are not included in `uim current`.

User uv configuration follows uv's platform conventions, including
`~/.config/uv/uv.toml` with XDG support on Linux and macOS and
`%APPDATA%\uv\uv.toml` on Windows. Custom uim entries use the platform's uim user
configuration directory.

## Conflict recovery

uim normally writes a scalar `default-index`. A simple anonymous structured default such as:

```toml
[[index]]
url = "https://old.example/simple"
default = true
```

can be replaced safely. A user-level `uv.toml` default containing only `name`, `url`, and
`default` is updated in place so `uim use <name>` remains compatible with uv's named-index
format. Named defaults in `pyproject.toml`, duplicate target names, authentication behavior,
publish URLs, and other extra semantics are left unchanged and reported as conflicts for
manual review. uim also refuses malformed TOML and leaves the original file unchanged when
parsing, validation, or atomic replacement fails.

## Security boundaries

- Catalog URLs containing embedded usernames, passwords, or tokens are rejected.
- uim does not maintain a credential store or print URL credentials in errors.
- Configure private-index credentials with uv's supported authentication mechanisms.
- TLS verification remains enabled during `uim test`.
- Supplying a browser launches an argument vector directly; uim does not construct a
  shell command.

## Development

```console
uv sync --locked
uv run pytest
uv run ruff check .
uv build
```

# mirr

[GitHub](https://github.com/hellojinjie/mirr) | [简体中文](README.md) | English

Default package sources (PyPI, the npm registry, etc.) can be slow or flaky on some
networks, so many people switch to a mirror - but uv, pip, npm, and conda each configure
mirrors differently.

`mirr` (short for "mirror", styled after [nrm](https://github.com/Pana/nrm)'s command
shape) manages
mirror/index configuration for these tools through one consistent set of commands
(`ls`/`use`/`add`/`del`/`rename`/`home`/`test`/`current`), currently covering
[uv](https://docs.astral.sh/uv/), pip, npm, and conda (read-only), while respecting each
tool's own user, project, environment, and multi-index configuration semantics.

## Quick start

Requires Python 3.9 or later.

```console
$ uv tool install mirr
```

### Test uv's mirrors and switch to the fastest one

```console
$ mirr uv test
[uv] * pypi -------- 187 ms
[uv]   tsinghua ---- 43 ms
[uv]   aliyun ------ 96 ms
[uv]   tencent ----- 121 ms
[uv]   huawei ------ 88 ms
[uv]   ustc -------- 104 ms

$ mirr uv use tsinghua
[uv] SUCCESS The index has been changed to 'tsinghua'.

$ mirr uv current
[uv] You are using tsinghua index.
```

Every line carries a `[tool]` prefix stating which tool's mirror configuration it
affects (the `uv` above can also be dropped - see "Multi-tool support" below).

Run `mirr use` without a name in an interactive terminal to choose from the catalog.
For scripts, always provide the name explicitly.

## Installation

mirr itself is a Python command-line tool - whether you mainly use pip, npm, or conda,
you only need to install mirr once (as above, or with `pip install mirr`), and managing
mirrors for those tools needs nothing further.

Prefer not to install anything? Run it on the fly with
[`uvx`](https://docs.astral.sh/uv/guides/tools/) by swapping in `uvx mirr ...`. From a
checkout, for development:

```console
git clone https://github.com/hellojinjie/mirr
cd mirr
uv tool install .
mirr --version
```

## Multi-tool support (uv / pip / npm / conda)

Commands default to operating on uv - the bare form is always equivalent to
`mirr uv <verb>` - and mirr also supports an explicit `mirr <tool> <verb>` form to
target pip, npm, or conda:

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
| `uv` | all | project `uv.toml`/`pyproject.toml` | identical to the bare (no-prefix) commands |
| `pip` | all | the active virtualenv | pip has no project-level config; `--local` errors without an active venv |
| `npm` | all | the current directory's `.npmrc` | scope overrides (e.g. `@corp:registry=`) are always preserved |
| `conda` | `ls`, `test` only | not applicable | channels are an ordered list, not a single default; write support is deferred, and `use`/`add`/`del`/`rename`/`current`/`home` clearly report as unsupported |

`mirr <tool> --help` only lists the commands that tool currently supports.

Authentication, publishing, npm scopes, and package-specific uv source bindings are
not managed by the initial mirr release.

## Commands

These commands are described in their bare form (operating on uv by default); pip and
npm take the same arguments and produce the same output format - swap in `mirr pip <verb>`
or `mirr npm <verb>`. The differences are each tool's config file locations, environment
variable names, `--local`'s scope (see the table above), and how `mirr test` builds its
probe request (see that section).

### `mirr ls`

```console
$ mirr uv ls
[uv]   pypi     --- https://pypi.org/simple
[uv] * tsinghua --- https://pypi.tuna.tsinghua.edu.cn/simple
[uv]   aliyun   --- https://mirrors.aliyun.com/pypi/simple
[uv]   tencent  --- https://mirrors.cloud.tencent.com/pypi/simple
[uv]   huawei   --- https://repo.huaweicloud.com/repository/pypi/simple
[uv]   ustc     --- https://mirrors.ustc.edu.cn/pypi/simple
```

Lists built-in and custom entries. The `*` marks the index effective in the current
directory, not merely the last user-level selection.

### `mirr current`

Prints the effective index as a plain sentence. It shows the catalog name when the
effective URL is known, `--show-url` substitutes the URL, and an uncataloged URL
is followed by the `mirr add` command needed to catalog it.

```console
mirr current --show-url
mirr current -u
mirr current --verbose
```

Verbose output includes the source and configuration path where applicable.

### `mirr use [name]`

Changes uv's user-level default index (writing a structured `[[index]] default = true`
entry) while preserving unrelated settings and named supplemental indexes.

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

`mirr add <name> <url> [home]`: `url` is the index address (required), `home` is a
homepage address used by `mirr home` (optional - omit it and `mirr home` won't work for
that entry). Built-in entries cannot be renamed or deleted. An active custom entry must
be replaced by another selection before deletion.

### Homepages and reachability

```console
mirr home pypi
mirr home pypi firefox   # the second argument picks which browser to open
mirr test pypi
mirr test
mirr test --timeout 10
```

`mirr test` (uv/pip) performs a lightweight, TLS-verified `HEAD` request against the
`pip/` project page beneath each Simple Repository endpoint; it never downloads the root
index. npm instead probes the registry root, and conda probes the channel's
`noarch/repodata.json` - same idea, different endpoint. If a server does not support
`HEAD`, mirr sends a `GET` instead and reads at most one byte. All-entry tests use bounded
concurrency and print results in catalog order. `*` marks the effective current index,
columns are aligned, and the fastest successful result is highlighted. This is a
reachability and latency check, not a package-download throughput benchmark.

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

Each tool's custom catalog is stored separately: `~/.config/mirr/{uv,pip,npm,conda}.toml`
on Linux/macOS, `%APPDATA%\mirr\{uv,pip,npm,conda}.toml` on Windows. If you used an older,
uv-only version of mirr, a leftover `config.toml` is recognized as-is as uv's catalog file
- no manual migration needed.

## Write format and conflict handling

The rules below are specific to uv's TOML config - pip's `pip.conf` and npm's `.npmrc`
are each just a single key-value pair (`index-url`/`registry`), so mirr simply overwrites
that value, with none of the named-entry or conflict-detection complexity described here.

mirr writes uv's recommended structured form, `[[index]] default = true`, not the scalar
`index-url` that uv's own docs mark as legacy. Note that `default-index` itself is never a
valid config-file field - it's only the name of the `--default-index` CLI flag and the
`UV_DEFAULT_INDEX` environment variable, and writing it as a field would make uv fail to
parse the config. If a legacy `index-url` scalar already exists, it is removed when the new
structured default is written, so the config never ends up with two conflicting defaults.

In the user-level `uv.toml`, mirr tags the entry it writes with a catalog name (e.g.
`name = "tsinghua"`), and updates that entry in place on the next `mirr use <name>` instead of
appending new ones:

```toml
[[index]]
name = "tsinghua"
url = "https://pypi.tuna.tsinghua.edu.cn/simple"
default = true
```

`pyproject.toml` is usually shared and reviewed by a team, so the default mirr writes there is
**unnamed** (`[[tool.uv.index]] url = "..." default = true`), and mirr never renames or rewrites
an existing named default there - that's treated as a conflict for manual resolution.

In any of these cases, mirr refuses to act automatically, leaves the file untouched, and
reports a conflict for manual resolution:

- The existing default carries fields beyond `name`, `url`, and `default` (unknown
  semantics like `explicit` or `authenticate`)
- There are multiple `default = true` entries
- Switching would collide with another named entry
- The TOML itself is malformed (parsing, validation, or atomic replacement fails)

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

# @hellojinjie/mirr

A tiny, dependency-free Node CLI for viewing and switching the **user-level**
npm registry. It is a standalone companion to the Python
[`mirr`](../README.md) tool, for environments that only have Node/npm
installed (no Python/uv required).

## Install

```sh
npm install -g @hellojinjie/mirr
```

This installs a `mirr` executable. Requires Node.js 18 or newer.

> **Naming note:** the Python `mirr` project also installs a command named
> `mirr`. Install one or the other in a given environment — the two are
> separate, independently-installed implementations and this package does
> not attempt to detect or resolve that conflict at runtime.

## Commands

```
mirr ls                 List the built-in registries, marking the current one
mirr current            Show the currently effective registry
mirr current -u         Show the effective registry URL instead of its name
mirr current -v         Also show where the value came from (and its path)
mirr use <name>         Switch the user-level registry (writes ~/.npmrc)
mirr test [name]        Probe one registry or all of them for reachability
```

Built-in registries: `npmjs`, `npmmirror`, `tencent`, `huawei`.

## Scope of this first version

This is intentionally a minimal subset of what the Python `mirr npm`
subcommand supports:

- **User-level only.** `mirr current`/`mirr ls` resolve the effective
  registry from the `npm_config_registry` environment variable and
  `~/.npmrc` only — they do **not** read a project-level `.npmrc` in the
  current directory, even though real npm would prefer that one.
- **No custom registries.** There is no `add`/`del`/`rename`/`home`; the
  registry list is the fixed built-in table above.
- **No `--local` switch and no interactive picker.** `mirr use` always
  requires an explicit name and always writes the user-level `~/.npmrc`.

## Editing behavior

`mirr use` only replaces the standalone `registry=...` line in `~/.npmrc`;
comments and scoped overrides (`@corp:registry=...`) are left untouched, and
the file is replaced atomically (written to a temp file in the same
directory, then renamed into place).

## Tests

```sh
npm test
```

Runs the built-in Node test runner (`node --test`); no dependencies to
install first.

## Why

`mirr --help` currently shows one flat, alphabetically-sorted `Commands:` list mixing the 4 package-tool entry points (`uv`/`pip`/`npm`/`conda`) with the 8 historical bare-verb aliases (`ls`/`use`/...). Nothing in that output shows what a given tool actually supports (e.g. that `conda` only has `ls`/`test`), that the bare verbs are just `uv` under another name, or that `uv` is the implicit default tool. A first-time user has to already know the multi-tool shape to make sense of the list.

## What Changes

- `mirr --help`'s `Usage:` line becomes `mirr [OPTIONS] [PACKAGE TOOL] COMMAND [ARGS]...`, naming the optional tool slot explicitly instead of Click's generic `COMMAND [ARGS]...`.
- The `Commands:` section splits into two labeled groups: `Package tools (uv is the default when [PACKAGE TOOL] is omitted):` (the 4 tool entry points) and `Commands:` (the 8 bare aliases) — pure display grouping, the underlying Command objects and their identity (bare alias == `mirr uv <verb>`) are untouched.
- An epilog line spells out the supported tools and points to `mirr <tool> --help` for that tool's actual supported verbs (noting conda's read-only subset as the concrete example).

## Capabilities

### Modified Capabilities
- `mirr-cli-dispatch`: the existing "向后兼容别名" and "工具专属帮助" requirements are unaffected in behavior; this adds a new requirement for the top-level help's presentation (Usage line wording, grouped display, epilog) so it explicitly states supported tools and the default.

## Impact

- `src/mirr/cli.py`: `_MirrGroup`/`cli` gain a custom `subcommand_metavar`, an `epilog`, and a `format_commands` override that groups `SUPPORTED_TOOLS` separately from the bare-alias verbs. No change to command registration, dispatch, or the alias-identity mechanism.
- Tests: new/updated assertions on `mirr --help` output (Usage line wording, section headers, epilog text).

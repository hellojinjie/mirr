## Context

See proposal.md - Why. `cli.py`'s top-level `cli` is a plain `click.Group` (via the `_MirrGroup` subclass added in multi-tool-mirror-support) with all 12 commands (4 tool groups + 8 bare aliases) registered flat; Click renders a single alphabetically-sorted `Commands:` section with a generic `COMMAND [ARGS]...` usage placeholder.

## Goals / Non-Goals

**Goals:**
- Make the top-level `--help` state, without a follow-up command, what a "package tool" slot is, which tools exist, and what the default is.

**Non-Goals:**
- Changing command dispatch, registration, or the alias-identity mechanism (bare verbs stay the exact same `Command` objects as `mirr uv <verb>`).
- Changing any tool's own `--help` (`mirr <tool> --help` is untouched).

## Decisions

- **Usage line wording**: set `subcommand_metavar = "[PACKAGE TOOL] COMMAND [ARGS]..."` on `_MirrGroup`. This is a public, documented Click `MultiCommand` attribute used verbatim to build the `Usage:` line - no need to override `collect_usage_pieces` or any parsing logic.
- **Grouped command listing**: override `format_commands` on `_MirrGroup` to partition `self.list_commands(ctx)` into `SUPPORTED_TOOLS` (labeled `Package tools (uv is the default when [PACKAGE TOOL] is omitted):`) and everything else (labeled `Commands:`), writing each as its own `click.HelpFormatter.section`. This only affects rendering; `self.commands` and dispatch are untouched.
- **Epilog**: a static string on the `@click.group(...)` decorator naming the four tools and pointing to `mirr <tool> --help`, with conda's read-only subset as the concrete example (matches what a first-time user hits first).

**Alternative considered**: hiding the 8 bare aliases from the top-level listing (`hidden=True`). Rejected - aliases are the exact same `Command` object shared with `mirr uv`'s subgroup, so `hidden` would hide them from both listings, not just the top level, without a wrapper layer this change doesn't need.

## Risks / Trade-offs

- [`format_commands` override is Click-version-sensitive private-ish API surface] → Mitigated by using the same public `HelpFormatter.section`/`write_dl` calls Click's own default implementation uses, and covering the exact rendered output with tests.

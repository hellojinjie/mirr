"""Command-line interface for mirr."""

from __future__ import annotations

import sys
from pathlib import Path
from typing import Optional

import click

from mirr import __version__
from mirr.backends.base import Backend, ConfigEditorError, ConfigError
from mirr.backends.conda import CondaBackend
from mirr.backends.npm import NpmBackend
from mirr.backends.pip import PipBackend
from mirr.backends.uv import UvBackend
from mirr.browser import BrowserError, open_index_home
from mirr.catalog import CatalogError, CatalogStore, Index, match_catalog_name, normalize_url
from mirr.probe import ProbeResult, probe_index, probe_indexes

_ALL_VERBS = ("ls", "current", "use", "add", "del", "rename", "home", "test")
SUPPORTED_TOOLS = ("uv", "pip", "npm", "conda")


def _is_interactive() -> bool:
    return sys.stdin.isatty()


def _catalog(tool: str) -> CatalogStore:
    return CatalogStore(tool=tool)


def _echo(tool: str, message: str, **kwargs: object) -> None:
    click.echo(f"[{tool}] {message}", **kwargs)


def _click_error(tool: str, error: Exception) -> click.ClickException:
    return click.ClickException(f"[{tool}] {error}")


def _make_ls_command(tool: str, backend: Backend) -> click.Command:
    supports_current = "current" in backend.SUPPORTED_VERBS

    @click.command("ls", help="List all indexes.")
    def ls_command() -> None:
        try:
            entries = _catalog(tool).entries()
            effective = backend.resolve_effective(start=Path.cwd()) if supports_current else None
        except (CatalogError, ConfigError) as exc:
            raise _click_error(tool, exc) from exc
        current_name = (
            match_catalog_name(effective.url, entries) if effective is not None else None
        )
        width = max(len(name) for name in entries)
        for name, index in entries.items():
            marker = "*" if name == current_name else " "
            _echo(tool, f"{marker} {name.ljust(width)} --- {index.url}")
        if effective is not None and current_name is None:
            _echo(tool, f"Current: {effective.url}")

    return ls_command


def _make_current_command(tool: str, backend: Backend) -> click.Command:
    @click.command("current", help="Show the current index name or URL.")
    @click.option("--show-url", "show_url", "-u", is_flag=True, help="Show the index URL.")
    @click.option("--verbose", "verbose", "-v", is_flag=True, help="Show configuration source.")
    def current_command(show_url: bool, verbose: bool) -> None:
        try:
            entries = _catalog(tool).entries()
            effective = backend.resolve_effective(start=Path.cwd())
        except (CatalogError, ConfigError) as exc:
            raise _click_error(tool, exc) from exc
        name = match_catalog_name(effective.url, entries)
        if name is None:
            _echo(tool, f"Your current index({effective.url}) is not included in the mirr indexes.")
            _echo(tool, "Use the mirr add <name> <url> [home] command to add it.")
        else:
            value = effective.url if show_url else name
            _echo(tool, f"You are using {click.style(value, fg='green')} index.")
        if verbose:
            if not show_url and name is not None:
                _echo(tool, f"URL: {effective.url}")
            _echo(tool, f"Source: {effective.source}")
            if effective.path is not None:
                _echo(tool, f"Path: {effective.path}")

    return current_command


def _make_use_command(tool: str, backend: Backend) -> click.Command:
    @click.command("use", help="Change the current index.")
    @click.argument("name", required=False)
    @click.option("--local", "local", "-l", is_flag=True, help="Switch the project index.")
    @click.option("--yes", "assume_yes", "-y", is_flag=True, help="Confirm file creation.")
    def use_command(name: Optional[str], local: bool, assume_yes: bool) -> None:
        store = _catalog(tool)
        try:
            entries = store.entries()
            if name is None:
                if not _is_interactive():
                    raise CatalogError("index name is required when input is not interactive")
                name = click.prompt("Index", type=click.Choice(list(entries), case_sensitive=True))
            selected = store.get(name)

            target = backend.locate_targets(local=local, start=Path.cwd())
            if local and not target.exists and not assume_yes:
                if not _is_interactive():
                    raise ConfigEditorError(
                        f"creating {target.path} requires --yes when input is not interactive"
                    )
                if not click.confirm(f"Create {target.path}?", default=False):
                    raise ConfigEditorError("local index switch cancelled")

            backend.apply_default(target, selected.url, index_name=name)
            _echo(tool, f"SUCCESS The index has been changed to '{name}'.")

            effective = backend.resolve_effective(start=Path.cwd())
            if not local and normalize_url(effective.url) != normalize_url(selected.url):
                _echo(
                    tool,
                    f"Warning: {effective.source} still overrides the user-level index.",
                    err=True,
                )
        except (CatalogError, ConfigError, ConfigEditorError) as exc:
            raise _click_error(tool, exc) from exc

    return use_command


def _make_add_command(tool: str, backend: Backend) -> click.Command:
    @click.command("add", help="Add a custom index.")
    @click.argument("name")
    @click.argument("url")
    @click.argument("home", required=False)
    def add_command(name: str, url: str, home: Optional[str]) -> None:
        try:
            _catalog(tool).add(name, url, home)
        except CatalogError as exc:
            raise _click_error(tool, exc) from exc
        _echo(tool, f"SUCCESS The index '{name}' has been added.")

    return add_command


def _make_delete_command(tool: str, backend: Backend) -> click.Command:
    @click.command("del", help="Delete a custom index.")
    @click.argument("name", required=False)
    def delete_command(name: Optional[str]) -> None:
        try:
            store = _catalog(tool)
            entries = store.entries()
            if name is None:
                if not _is_interactive():
                    raise CatalogError("index name is required when input is not interactive")
                custom_names = [
                    entry_name for entry_name, index in entries.items() if not index.builtin
                ]
                if not custom_names:
                    raise CatalogError("there are no custom indexes to delete")
                name = click.prompt("Index", type=click.Choice(custom_names, case_sensitive=True))
            active_urls = backend.managed_urls(start=Path.cwd())
            store.delete(name, active_urls=active_urls)
        except (CatalogError, ConfigError) as exc:
            raise _click_error(tool, exc) from exc
        _echo(tool, f"SUCCESS The index '{name}' has been deleted.")

    return delete_command


def _make_rename_command(tool: str, backend: Backend) -> click.Command:
    @click.command("rename", help="Rename a custom index.")
    @click.argument("name")
    @click.argument("new_name")
    def rename_command(name: str, new_name: str) -> None:
        try:
            _catalog(tool).rename(name, new_name)
        except CatalogError as exc:
            raise _click_error(tool, exc) from exc
        _echo(tool, f"SUCCESS The index '{name}' has been renamed to '{new_name}'.")

    return rename_command


def _make_home_command(tool: str, backend: Backend) -> click.Command:
    @click.command("home", help="Open an index homepage.")
    @click.argument("name")
    @click.argument("browser", required=False)
    def home_command(name: str, browser: Optional[str]) -> None:
        try:
            index = _catalog(tool).get(name)
            open_index_home(index, browser)
        except (CatalogError, BrowserError) as exc:
            raise _click_error(tool, exc) from exc
        _echo(tool, f"Opened the homepage for '{name}'.")

    return home_command


def _make_test_command(tool: str, backend: Backend) -> click.Command:
    supports_current = "current" in backend.SUPPORTED_VERBS

    def probe(index: Index, timeout: float) -> ProbeResult:
        spec = backend.build_probe_request(index)
        return probe_index(index, timeout, build_probe_url=lambda _url: spec.url)

    @click.command("test", help="Test index reachability.")
    @click.argument("name", required=False)
    @click.option("--timeout", type=click.FloatRange(min=0.1), default=5.0, show_default=True)
    def test_command(name: Optional[str], timeout: float) -> None:
        try:
            store = _catalog(tool)
            entries = store.entries()
            indexes = [store.get(name)] if name is not None else list(entries.values())
            effective = backend.resolve_effective(start=Path.cwd()) if supports_current else None
        except (CatalogError, ConfigError) as exc:
            raise _click_error(tool, exc) from exc

        results = probe_indexes(indexes, timeout=timeout, probe=probe)
        current_name = (
            match_catalog_name(effective.url, entries) if effective is not None else None
        )
        fastest = None
        if name is None:
            successful_latencies = [
                result.latency_ms for result in results if result.ok and result.latency_ms is not None
            ]
            if successful_latencies:
                fastest = min(successful_latencies)

        width = max(len(result.name) for result in results) + 3
        failed = False
        for result in results:
            prefix = click.style("* ", fg="green", bold=True) if result.name == current_name else "  "
            dash_count = max(1, width - len(result.name) + 1)
            separator = click.style("-" * dash_count, dim=True)
            if result.ok:
                suffix = f"{result.latency_ms:.0f} ms"
                if fastest is not None and result.latency_ms == fastest:
                    suffix = click.style(suffix, bg="bright_green")
            else:
                failed = True
                suffix = result.error or "Fetch error"
            _echo(tool, f"{prefix}{result.name} {separator} {suffix}")
        if failed:
            raise click.exceptions.Exit(1)

    return test_command


_COMMAND_FACTORIES = {
    "ls": _make_ls_command,
    "current": _make_current_command,
    "use": _make_use_command,
    "add": _make_add_command,
    "del": _make_delete_command,
    "rename": _make_rename_command,
    "home": _make_home_command,
    "test": _make_test_command,
}


def _make_unsupported_command(tool: str, verb: str) -> click.Command:
    @click.command(verb, hidden=True)
    @click.argument("args", nargs=-1)
    def stub_command(args: tuple[str, ...]) -> None:
        raise click.ClickException(f"[{tool}] '{verb}' is not supported yet.")

    return stub_command


def _build_tool_group(tool: str, backend: Backend) -> click.Group:
    group = click.Group(name=tool, help=f"Manage {tool} package indexes.")
    for verb in _ALL_VERBS:
        if verb in backend.SUPPORTED_VERBS:
            group.add_command(_COMMAND_FACTORIES[verb](tool, backend))
        else:
            group.add_command(_make_unsupported_command(tool, verb))
    return group


class _MirrGroup(click.Group):
    """Top-level group that reports unknown tools with the supported-tool list."""

    def resolve_command(self, ctx: click.Context, args: list[str]):
        try:
            return super().resolve_command(ctx, args)
        except click.UsageError as exc:
            attempted = args[0] if args else ""
            if attempted and attempted not in self.commands:
                raise click.UsageError(
                    f"'{attempted}' is not a supported tool. "
                    f"Supported tools: {', '.join(SUPPORTED_TOOLS)}.",
                    ctx=ctx,
                ) from exc
            raise


@click.group(cls=_MirrGroup, context_settings={"help_option_names": ["-h", "--help"]})
@click.version_option(__version__, prog_name="mirr")
def cli() -> None:
    """Manage package indexes for uv, pip, npm, and conda."""


_BACKENDS: dict[str, Backend] = {
    "uv": UvBackend(),
    "pip": PipBackend(),
    "npm": NpmBackend(),
    "conda": CondaBackend(),
}

for _tool_name, _backend in _BACKENDS.items():
    cli.add_command(_build_tool_group(_tool_name, _backend), name=_tool_name)

# Backward-compatible aliases: bare `mirr <verb>` is exactly `mirr uv <verb>`
# (the same Command object, so behavior is identical by construction).
_uv_group = cli.commands["uv"]
for _verb in _ALL_VERBS:
    cli.add_command(_uv_group.commands[_verb], name=_verb)

del _tool_name, _backend, _uv_group, _verb


if __name__ == "__main__":
    cli()

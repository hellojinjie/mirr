"""Command-line interface for uim."""

from __future__ import annotations

import sys
from pathlib import Path
from typing import Optional

import click

from uim import __version__
from uim.browser import BrowserError, open_index_home
from uim.catalog import CatalogError, CatalogStore, normalize_url
from uim.config import (
    ConfigError,
    LocalTarget,
    find_local_target,
    managed_default_urls,
    match_catalog_name,
    resolve_effective_index,
    user_uv_config_path,
)
from uim.editor import ConfigEditorError, set_default_index
from uim.probe import probe_indexes


def _is_interactive() -> bool:
    return sys.stdin.isatty()


def _catalog() -> CatalogStore:
    return CatalogStore()


def _effective():
    return resolve_effective_index(start=Path.cwd())


def _click_error(error: Exception) -> click.ClickException:
    return click.ClickException(str(error))


@click.group(context_settings={"help_option_names": ["-h", "--help"]})
@click.version_option(__version__, prog_name="uim")
def cli() -> None:
    """Manage uv package indexes quickly."""


@cli.command("ls")
def list_indexes() -> None:
    """List all indexes."""

    try:
        entries = _catalog().entries()
        effective = _effective()
    except (CatalogError, ConfigError) as exc:
        raise _click_error(exc) from exc
    current_name = match_catalog_name(effective.url, entries)
    width = max(len(name) for name in entries)
    for name, index in entries.items():
        marker = "*" if name == current_name else " "
        click.echo(f"{marker} {name.ljust(width)} --- {index.url}")
    if current_name is None:
        click.echo(f"Current: {effective.url}")


@cli.command()
@click.option("--show-url", "show_url", "-u", is_flag=True, help="Show the index URL.")
@click.option("--verbose", "verbose", "-v", is_flag=True, help="Show configuration source.")
def current(show_url: bool, verbose: bool) -> None:
    """Show the current index name or URL."""

    try:
        entries = _catalog().entries()
        effective = _effective()
    except (CatalogError, ConfigError) as exc:
        raise _click_error(exc) from exc
    name = match_catalog_name(effective.url, entries)
    if name is None:
        click.echo(f"Your current index({effective.url}) is not included in the uim indexes.")
        click.echo("Use the uim add <name> <url> [home] command to add it.")
    else:
        value = effective.url if show_url else name
        click.echo(f"You are using {click.style(value, fg='green')} index.")
    if verbose:
        if not show_url and name is not None:
            click.echo(f"URL: {effective.url}")
        click.echo(f"Source: {effective.source}")
        if effective.path is not None:
            click.echo(f"Path: {effective.path}")


@cli.command()
@click.argument("name", required=False)
@click.option("--local", "local", "-l", is_flag=True, help="Switch the project index.")
@click.option("--yes", "assume_yes", "-y", is_flag=True, help="Confirm file creation.")
def use(name: Optional[str], local: bool, assume_yes: bool) -> None:
    """Change the current index."""

    store = _catalog()
    try:
        entries = store.entries()
        if name is None:
            if not _is_interactive():
                raise CatalogError("index name is required when input is not interactive")
            name = click.prompt("Index", type=click.Choice(list(entries), case_sensitive=True))
        selected = store.get(name)

        if local:
            target = find_local_target(Path.cwd())
            if not target.exists and not assume_yes:
                if not _is_interactive():
                    raise ConfigEditorError(
                        f"creating {target.path} requires --yes when input is not interactive"
                    )
                if not click.confirm(f"Create {target.path}?", default=False):
                    raise ConfigEditorError("local index switch cancelled")
        else:
            path = user_uv_config_path()
            target = LocalTarget(path=path, kind="uv", exists=path.exists())

        set_default_index(target, selected.url, index_name=name)
        click.echo(f"SUCCESS The index has been changed to '{name}'.")

        effective = _effective()
        if not local and normalize_url(effective.url) != normalize_url(selected.url):
            click.echo(
                f"Warning: {effective.source} still overrides the user-level index.",
                err=True,
            )
    except (CatalogError, ConfigError, ConfigEditorError) as exc:
        raise _click_error(exc) from exc


@cli.command()
@click.argument("name")
@click.argument("url")
@click.argument("home", required=False)
def add(name: str, url: str, home: Optional[str]) -> None:
    """Add a custom index."""

    try:
        _catalog().add(name, url, home)
    except CatalogError as exc:
        raise _click_error(exc) from exc
    click.echo(f"SUCCESS The index '{name}' has been added.")


@cli.command("del")
@click.argument("name", required=False)
def delete(name: Optional[str]) -> None:
    """Delete a custom index."""

    try:
        store = _catalog()
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
        active_urls = managed_default_urls(start=Path.cwd())
        store.delete(name, active_urls=active_urls)
    except (CatalogError, ConfigError) as exc:
        raise _click_error(exc) from exc
    click.echo(f"SUCCESS The index '{name}' has been deleted.")


@cli.command()
@click.argument("name")
@click.argument("new_name")
def rename(name: str, new_name: str) -> None:
    """Rename a custom index."""

    try:
        _catalog().rename(name, new_name)
    except CatalogError as exc:
        raise _click_error(exc) from exc
    click.echo(f"SUCCESS The index '{name}' has been renamed to '{new_name}'.")


@cli.command()
@click.argument("name")
@click.argument("browser", required=False)
def home(name: str, browser: Optional[str]) -> None:
    """Open an index homepage."""

    try:
        index = _catalog().get(name)
        open_index_home(index, browser)
    except (CatalogError, BrowserError) as exc:
        raise _click_error(exc) from exc
    click.echo(f"Opened the homepage for '{name}'.")


@cli.command()
@click.argument("name", required=False)
@click.option("--timeout", type=click.FloatRange(min=0.1), default=5.0, show_default=True)
def test(name: Optional[str], timeout: float) -> None:
    """Test index reachability."""

    try:
        store = _catalog()
        entries = store.entries()
        indexes = [store.get(name)] if name is not None else list(entries.values())
        effective = _effective()
    except (CatalogError, ConfigError) as exc:
        raise _click_error(exc) from exc

    results = probe_indexes(indexes, timeout=timeout)
    current_name = match_catalog_name(effective.url, entries)
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
        click.echo(f"{prefix}{result.name} {separator} {suffix}")
    if failed:
        raise click.exceptions.Exit(1)


if __name__ == "__main__":
    cli()

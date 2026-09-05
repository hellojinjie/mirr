from __future__ import annotations

import click
from click.testing import CliRunner
from conftest import IsolatedEnvironment

from mirr.cli import cli
from mirr.probe import ProbeResult


def test_current_uses_nrm_shaped_sentence_for_name_url_and_verbose_provenance(
    isolated_env: IsolatedEnvironment,
) -> None:
    runner = CliRunner()
    switched = runner.invoke(cli, ["use", "tencent"])
    assert switched.exit_code == 0, switched.output

    named = runner.invoke(cli, ["current"])
    url = runner.invoke(cli, ["current", "--show-url"])
    verbose = runner.invoke(cli, ["current", "--verbose"])

    assert named.output == "[uv] You are using tencent index.\n"
    assert url.output == (
        "[uv] You are using https://mirrors.cloud.tencent.com/pypi/simple index.\n"
    )
    assert verbose.output == (
        "[uv] You are using tencent index.\n"
        "[uv] URL: https://mirrors.cloud.tencent.com/pypi/simple\n"
        "[uv] Source: user:uv.toml\n"
        f"[uv] Path: {isolated_env.user_uv_config}\n"
    )


def test_current_explains_how_to_catalog_an_unknown_effective_url(
    isolated_env: IsolatedEnvironment,
    monkeypatch,
) -> None:
    monkeypatch.setenv("UV_DEFAULT_INDEX", "https://unknown.example/simple")

    result = CliRunner().invoke(cli, ["current"])

    assert result.exit_code == 0
    assert result.output == (
        "[uv] Your current index(https://unknown.example/simple) is not included in the mirr "
        "indexes.\n"
        "[uv] Use the mirr add <name> <url> [home] command to add it.\n"
    )


def test_test_output_marks_current_aligns_columns_and_highlights_fastest(
    isolated_env: IsolatedEnvironment,
    monkeypatch,
) -> None:
    def deterministic(indexes, **kwargs):
        latencies = {
            "pypi": 100.4,
            "tsinghua": 50.4,
            "tencent": 200.6,
            "huawei": 80.6,
            "ustc": 90.2,
        }
        return [
            ProbeResult(
                index.name,
                index.url,
                index.name != "aliyun",
                latencies.get(index.name),
                "TLS failure" if index.name == "aliyun" else None,
            )
            for index in indexes
        ]

    monkeypatch.setattr("mirr.cli.probe_indexes", deterministic)

    result = CliRunner().invoke(cli, ["test"], color=True)

    assert result.exit_code == 1
    assert click.unstyle(result.output) == (
        "[uv] * pypi -------- 100 ms\n"
        "[uv]   tsinghua ---- 50 ms\n"
        "[uv]   aliyun ------ TLS failure\n"
        "[uv]   tencent ----- 201 ms\n"
        "[uv]   huawei ------ 81 ms\n"
        "[uv]   ustc -------- 90 ms\n"
    )
    assert click.style("* ", fg="green", bold=True) in result.output
    assert click.style("50 ms", bg="bright_green") in result.output


def test_single_test_marks_current_without_fastest_highlight(
    isolated_env: IsolatedEnvironment,
    monkeypatch,
) -> None:
    def successful(indexes, **kwargs):
        index = indexes[0]
        return [ProbeResult(index.name, index.url, True, 12.6, None)]

    monkeypatch.setattr("mirr.cli.probe_indexes", successful)

    result = CliRunner().invoke(cli, ["test", "pypi"], color=True)

    assert result.exit_code == 0
    assert click.unstyle(result.output) == "[uv] * pypi ---- 13 ms\n"
    assert "\x1b[102m" not in result.output

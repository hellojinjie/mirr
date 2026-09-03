from __future__ import annotations

from urllib.error import HTTPError

import pytest

from mirr.catalog import Index
from mirr.probe import ProbeResult, probe_index


class Response:
    status = 200

    def __init__(self) -> None:
        self.read_sizes: list[int] = []

    def read(self, size: int = -1) -> bytes:
        self.read_sizes.append(size)
        return b"x"

    def __enter__(self):
        return self

    def __exit__(self, exc_type, exc_value, traceback):
        return None


def test_probe_uses_head_on_lightweight_project_endpoint() -> None:
    requests = []
    response = Response()
    ticks = iter([10.0, 10.125])

    def open_request(request, timeout):
        requests.append((request, timeout))
        return response

    result = probe_index(
        Index("pypi", "https://pypi.example/simple"),
        opener=open_request,
        clock=lambda: next(ticks),
    )

    assert result == ProbeResult("pypi", "https://pypi.example/simple", True, 125.0, None)
    assert len(requests) == 1
    request, timeout = requests[0]
    assert request.full_url == "https://pypi.example/simple/pip/"
    assert request.get_method() == "HEAD"
    assert request.get_header("User-agent") == "mirr/0.1.0"
    assert timeout == 5.0
    assert response.read_sizes == []


@pytest.mark.parametrize("status", [405, 501])
def test_probe_falls_back_to_one_byte_ranged_get_when_head_is_unsupported(
    status: int,
) -> None:
    requests = []
    response = Response()
    ticks = iter([10.0, 10.25])

    def open_request(request, timeout):
        requests.append(request)
        if len(requests) == 1:
            raise HTTPError(request.full_url, status, "unsupported", {}, None)
        return response

    result = probe_index(
        Index("mirror", "https://mirror.example/simple/"),
        opener=open_request,
        clock=lambda: next(ticks),
    )

    assert result.ok
    assert result.latency_ms == 250.0
    assert [request.full_url for request in requests] == [
        "https://mirror.example/simple/pip/",
        "https://mirror.example/simple/pip/",
    ]
    assert [request.get_method() for request in requests] == ["HEAD", "GET"]
    assert requests[1].get_header("Range") == "bytes=0-0"
    assert requests[1].get_header("User-agent") == "mirr/0.1.0"
    assert response.read_sizes == [1]


def test_probe_does_not_fallback_for_other_http_errors() -> None:
    requests = []

    def open_request(request, timeout):
        requests.append(request)
        raise HTTPError(request.full_url, 403, "Forbidden", {}, None)

    result = probe_index(
        Index("private", "https://private.example/simple"),
        opener=open_request,
    )

    assert not result.ok
    assert result.error == "HTTP Error 403: Forbidden"
    assert len(requests) == 1
    assert requests[0].get_method() == "HEAD"

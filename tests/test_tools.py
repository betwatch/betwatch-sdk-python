"""The stream-timing tool is a launch gate, so it has to keep working."""

from __future__ import annotations

import importlib.util
from pathlib import Path


def _tool():
    path = Path(__file__).resolve().parents[1] / "tools" / "stream_timing.py"
    spec = importlib.util.spec_from_file_location("stream_timing", path)
    assert spec is not None and spec.loader is not None
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def test_defaults_to_the_widest_scope() -> None:
    args = _tool().parse_args([])
    assert args.sport is None and args.country is None
    assert args.require_attach is None, "no gate unless asked for"
    assert args.repeat == 1


def test_scope_and_gate_flags_parse() -> None:
    args = _tool().parse_args(
        ["--sport", "thoroughbred", "--country", "au", "--require-attach", "20", "--json"]
    )
    assert args.sport == ["thoroughbred"]
    assert args.country == ["au"]
    assert args.require_attach == 20.0
    assert args.json


def test_sport_is_restricted_to_the_public_vocabulary() -> None:
    import pytest

    with pytest.raises(SystemExit):
        _tool().parse_args(["--sport", "camel"])


def test_the_timer_measures_the_path_that_exists() -> None:
    """It opened snapshot=full, which is now refused above an event/meeting/venue.

    Ten attempts reported ten drops that were really ten 422s — a confident
    number measuring something gone. It reads /v2/events/snapshot and follows now.
    """
    from pathlib import Path

    source = (Path(__file__).resolve().parents[1] / "tools" / "stream_timing.py").read_text()
    assert "client.snapshot(" in source
    assert "client.follow(" in source
    assert 'snapshot="full"' not in source

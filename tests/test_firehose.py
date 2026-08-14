from __future__ import annotations

import importlib.util
from pathlib import Path


def _firehose():
    path = Path(__file__).resolve().parents[1] / "examples" / "firehose.py"
    spec = importlib.util.spec_from_file_location("firehose_example", path)
    assert spec is not None and spec.loader is not None
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def test_odds_delta_only_calls_first_seen_new() -> None:
    delta = _firehose()._odds_delta
    assert delta(None, 3.2) == "new"
    assert delta(3.2, 3.2) == "same"
    assert delta(3.2, 3.4) == "3.2->3.4"

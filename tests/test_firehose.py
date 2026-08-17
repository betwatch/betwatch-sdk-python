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


def test_example_parses_its_scope_flags() -> None:
    args = _firehose().parse_args(["--sport", "thoroughbred", "--country", "au"])
    assert args.sport == ["thoroughbred"]
    assert args.country == ["au"]


def test_example_defaults_to_the_widest_scope() -> None:
    args = _firehose().parse_args([])
    assert args.sport is None
    assert args.country is None


def test_example_leaves_dedup_and_progress_to_the_sdk() -> None:
    """The example demonstrates the API; it does not reimplement it.

    Both of these were hand-rolled here and are now SDK features. If they come
    back, the example has started growing its own client again.
    """
    source = (Path(__file__).resolve().parents[1] / "examples" / "firehose.py").read_text()
    assert "ChangeTracker" in source
    assert "progress=" in source
    assert "class _BootstrapProgress" not in source
    assert "_odds_delta" not in source

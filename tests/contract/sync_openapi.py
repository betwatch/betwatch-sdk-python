#!/usr/bin/env python
"""Refresh the vendored contract used by `tests/test_contract_spec.py`.

The SDK asserts its error codes, budget headers and operation coverage against
a committed copy of the published spec, so those checks run in CI without the
API repo checked out. This copies a fresh spec in; the tests then say whether
anything the SDK depends on moved.

    uv run tests/contract/sync_openapi.py [path-to-openapi.json]

Defaults to the sibling betwatch checkout, or $BETWATCH_OPENAPI when set.
"""

from __future__ import annotations

import json
import os
import shutil
import sys
from pathlib import Path

VENDORED = Path(__file__).resolve().parent / "openapi.json"
DEFAULT_SOURCE = Path.home() / "Projects/betwatch/apps/docs/public/api/openapi.json"


def source_path(argv: list[str]) -> Path:
    if len(argv) > 1:
        return Path(argv[1]).expanduser()
    env = os.environ.get("BETWATCH_OPENAPI")
    return Path(env).expanduser() if env else DEFAULT_SOURCE


def main(argv: list[str]) -> int:
    source = source_path(argv)
    if not source.is_file():
        print(f"no spec at {source}", file=sys.stderr)
        return 1

    spec = json.loads(source.read_text())
    version = spec.get("info", {}).get("version")
    operations = sum(
        1
        for path in spec.get("paths", {}).values()
        for method, op in path.items()
        if method == "get" and op.get("operationId")
    )
    if VENDORED.is_file() and VENDORED.read_bytes() == source.read_bytes():
        print(f"already current: {version}, {operations} operations")
        return 0

    shutil.copyfile(source, VENDORED)
    print(f"vendored {source} -> {VENDORED}")
    print(f"contract {version}, {operations} operations. Now run: uv run pytest")
    return 0


if __name__ == "__main__":
    raise SystemExit(main(sys.argv))

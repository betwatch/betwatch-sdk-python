#!/usr/bin/env bash
# Every gate CI runs, with an exit code you can trust.
#
# Exists because `uv run pytest | tail` reports tail's status, not pytest's,
# which let a commit leave this machine with a failing test twice in one day.
# Pipe anything in here and pipefail still catches it.
set -euo pipefail

cd "$(dirname "$0")/.."

fail=0
run() {
    local name=$1
    shift
    printf '%-14s' "$name"
    if output=$("$@" 2>&1); then
        printf 'ok\n'
    else
        printf 'FAILED\n'
        printf '%s\n' "$output" | tail -25
        fail=1
    fi
}

run lockfile uv lock --check
run format uv run ruff format --check
run lint uv run ruff check
run ty uv run ty check
run pyright uv run pyright
run tests uv run pytest -q

if [ "$fail" -ne 0 ]; then
    echo
    echo "gates failed — do not push"
    exit 1
fi
echo
echo "all gates passed"

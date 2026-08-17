# Betwatch Python SDK

[![PyPI - Version](https://img.shields.io/pypi/v/betwatch.svg)](https://pypi.org/project/betwatch)
[![PyPI - Python Version](https://img.shields.io/pypi/pyversions/betwatch.svg)](https://pypi.org/project/betwatch)

Public `/v1` REST + SSE client. **`2.0.0b1` on the `beta` branch** — not the
GraphQL 1.x `get_races` client.

Agents: read [`AGENTS.md`](AGENTS.md) first.

## Install

```console
pip install betwatch==2.0.0b1
# or, from the beta branch:
# pip install "betwatch @ git+https://github.com/betwatch/betwatch-sdk-python@beta"
```

Secrets live in a **gitignored** `fnox.toml`, encrypted to this machine's age
key (`~/.config/fnox/age.txt`). Ciphertext is not committed.

```console
fnox exec -- uv run examples/live_check.py          # local → http://127.0.0.1:8888
fnox exec --profile prod -- uv run examples/watch_event.py
```

Or set `BETWATCH_API_KEY` yourself. Optional `BETWATCH_API_URL` (default
`https://api-beta.betwatch.com`). `FNOX_PROFILE=prod` selects the hosted API.

## Usage

See [examples](examples) — the same use cases as 1.x (`get_races`,
`get_race_prices`, `subscriptions`), plus `firehose.py` for every
code with a resumable cursor, and `tui.py` for a Textual raceday grid.

### Discover, then price, then follow

The API is built around one workflow, and so is this client. Find races, ask
for their prices, then attach a stream at exactly the position the price read
returned.

```python
from betwatch import Betwatch, OddsFrame

with Betwatch() as client:
    # 1. Discover. /v1/odds and friends refuse an unscoped read, so start here.
    page = client.events.list(sport="thoroughbred", country="au", limit=5)
    event = page[0]
    print(event.name, event.start_at, event.racing.race_number)

    # 2. Price. The snapshot carries a stream cursor captured *before* it read,
    #    so nothing changes in the gap between pricing and following.
    card = client.events.snapshot(event.id)
    print(card.best_price(card.entrants[0]))

    # 3. Follow. follow() sends that cursor as Last-Event-ID with snapshot=none.
    with client.follow(card) as live:
        for frame in live:
            if isinstance(frame, OddsFrame):
                print(frame.data.source.id, frame.data.price)
```

`client.watch(event_id)` does all three in one call when you do not need the
snapshot yourself.

`snapshot(..., include="history")` fills `Odds.history` with each source's
fluctuations. It is honoured as of contract 1.0.0 and doubles the call's quota
cost, so ask for it only when you use it.

### Stream instead of polling

**Stream frames are not metered.** Polling `/v1/odds` on a timer is the
expensive way to stay current and the slowest to see a move; bootstrapping once
and following costs nothing beyond that first read. A single filtered
connection covers a whole raceday — `client.stream(sport="thoroughbred",
country="au")` — and a connection per race is the shape to avoid, which your
plan's concurrent-stream cap will enforce with `StreamLimitError`.

### Paging a collection

Every collection has `iter()`, which follows `next` until it stops coming:

```python
for venue in client.venues.iter(country="au"):
    print(venue.name)
```

A cursor belongs to the collection that issued it — a `next` from `/v1/venues`
is not valid on `/v1/meetings`. `iter()` feeds each cursor back to the endpoint
that produced it, so this cannot go wrong by accident. Cursors are opaque: do
not decode, build, or edit one.

### Handling failures

Every failure is an RFC 9457 problem document with a stable `code`. Branch on
the code (or on the exception type, which is selected from it), never on prose:

```python
import time

from betwatch import QuotaExceededError, RateLimitError

try:
    page = client.odds.list(event=event.id)
except RateLimitError as err:
    time.sleep(err.retry_after or 1)      # short window; worth waiting out
except QuotaExceededError as err:
    alert(f"monthly quota spent, resets {err.rate_limit.monthly_reset}")
```

`QuotaExceededError` is deliberately **not** a subclass of `RateLimitError`:
one resets in seconds, the other in weeks. The client retries `rate_limited`
and the 5xx codes for you, and fails fast on everything the docs mark as
non-retryable. Every exception carries `code`, `detail`, `errors`,
`request_id`, and `trace_id` — quote the last two to support.

### Operations

The client groups operations by resource, which is the Python idiom. The
mapping to the contract's `operationId`s is one-to-one:

| operationId | SDK |
|---|---|
| `listEvents` / `getEvent` / `getEventSnapshot` | `client.events.list` / `.retrieve` / `.snapshot` |
| `listEntrants` / `getEntrant` | `client.entrants.list` / `.retrieve` |
| `getCompetitor` | `client.competitors.retrieve` |
| `listMarkets` / `getMarket` | `client.markets.list` / `.retrieve` |
| `listOutcomes` / `getOutcome` | `client.outcomes.list` / `.retrieve` |
| `listOdds` / `getOdds` | `client.odds.list` / `.retrieve` |
| `listMeetings` / `getMeeting` | `client.meetings.list` / `.retrieve` |
| `listVenues` / `getVenue` | `client.venues.list` / `.retrieve` |
| `listSources` | `client.sources.list` |
| `streamRacing` | `client.stream` / `.watch` / `.follow` |

Dump to pandas without caring that the backend is msgspec:

```python
import pandas as pd

card = client.events.snapshot(event.id)
df = pd.DataFrame.from_records(card.to_records())
```

Sync and async clients share one resource tree (`AsyncBetwatch`).

Reads retry twice by default, driven by the problem `code` rather than the HTTP
status — the status cannot tell `rate_limited` from `quota_exceeded`, and both
are `429`. Set `max_retries=0` to disable retries or another non-negative value
to change the budget. Stream reconnect is separate: SSE reconnects only after
transport interruption, while HTTP, cursor, server frame, and decode failures
surface immediately.

`client.rate_limit` holds the budget headers from the last response — both the
per-minute window and the monthly quota, including when the quota resets.

The contract only grows. Unknown response fields (including `$schema`) are
ignored, unknown SSE frame names are no-ops, and a vocabulary value newer than
this release reads as `"unknown"` rather than failing to decode.

An event snapshot carries a required server-issued `stream` continuation. Pass
the complete snapshot to `client.follow(card)`; do not copy its cursor into a
new stream with reconstructed filters.

## TUI

`examples/tui.py` is a Textual demo (not part of the installed package). Left
pane is the raceday list **ordered by time-to-jump**; right pane is the runner
× bookmaker grid. The selected race follows live `/v1/stream`.

```console
uv sync
fnox exec -- uv run examples/tui.py
fnox exec -- uv run examples/tui.py --sport harness --country au
```

`1`/`2`/`3` switch code, `n` jumps to the next race, `w`/`p` is win/place,
`/` filters tracks, `?` is help.

## Development

```console
uv sync
uv run ruff check
uv run ty check
uv run pytest
```

The SDK's error codes, budget-header names, and operation coverage are pinned
against a committed copy of the published contract at
`tests/contract/openapi.json`. When the API ships a new spec:

```console
uv run tests/contract/sync_openapi.py     # or: BETWATCH_OPENAPI=/path/to/openapi.json
uv run pytest tests/test_contract_spec.py
```

A failure there names exactly what moved — a new error code with no retry
decision, a budget header nothing parses, an operation with no method.

### Measuring the stream

`tools/stream_timing.py` reports how long `/v1/stream` takes to bootstrap for a
given filter scope: time to `ready`, time to the first data frame, the silence
between them, and time to `sync`. A broad `snapshot=full` sends nothing for
tens of seconds while the server builds the snapshot, so the silence is the
number worth watching.

```console
fnox exec --profile prod -- uv run tools/stream_timing.py --sport thoroughbred --country au
fnox exec --profile prod -- uv run tools/stream_timing.py --json --require-sync 60
```

`--require-sync` exits non-zero if the bootstrap takes longer than that, so it
works as a regression gate.

Live check against a local API:

```console
export BETWATCH_API_KEY=bw_...
export BETWATCH_API_URL=http://localhost:8888
uv run examples/live_check.py run-1
```

## Releasing

Tag the exact version in `src/betwatch/__about__.py` (`v2.0.0b1`) and push the
tag. `.github/workflows/release.yml` builds that commit, checks the tag matches
the package version, and publishes with PyPI Trusted Publishing. Do not bump
versions from CI.

Changelog locally: `uv run git-cliff --unreleased`.

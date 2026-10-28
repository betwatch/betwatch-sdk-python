# Betwatch Python SDK

[![PyPI - Version](https://img.shields.io/pypi/v/betwatch.svg)](https://pypi.org/project/betwatch)
[![PyPI - Python Version](https://img.shields.io/pypi/pyversions/betwatch.svg)](https://pypi.org/project/betwatch)

Live Australian and New Zealand racing odds in Python: every race, every
runner, and the current price from every bookmaker, tote and exchange Betwatch
tracks, with a stream of changes as they happen.

```python
from betwatch import Betwatch

with Betwatch() as client:
    race = client.events.list(sport="thoroughbred", country="au", status="open").next_open
    card = client.events.snapshot(race.id)
    for runner in card.entrants:
        print(runner.number, runner.name, card.best_price(runner))
```

> **Beta.** `2.x` targets the Betwatch Racing API `/v2` and is in public beta.
> Pin the exact version; minor details may change before `2.0.0`. The `1.x`
> GraphQL client (`get_races`) is a different API and is not compatible.

## Install

```console
pip install --pre betwatch
```

`--pre` selects the 2.x beta. Pin the version you tested against, for example
`betwatch==2.0.0b4`.

Python 3.11+. The only dependencies are `httpx` and `msgspec`.
`pip install "betwatch[pandas]"` adds pandas for `to_records()` users.

## Authenticate

Create a key at [Account → API](https://beta.betwatch.com/account/api). The key
is shown once, so store it somewhere safe, then export it:

```console
export BETWATCH_API_KEY=bw_...
```

`Betwatch()` reads it from the environment, or pass `Betwatch(api_key=...)`.
The client talks to `https://api-beta.betwatch.com` unless you set
`BETWATCH_API_URL` or `base_url=`.

## The model

| Betwatch | Means |
|---|---|
| **Event** | One race. `client.events` |
| **Entrant** | A runner in a race. `card.entrants` |
| **Odds** | One source's current win or place price on one runner. `card.odds` |
| **Source** | A bookmaker, tote or exchange. `client.sources.list()` |
| **Meeting / Venue** | A day's racing at a track / the track itself |

Every response is a typed object with snake_case attributes, so your editor
completes `race.start_at`, `runner.racing.barrier` and `quote.source.id`.
Closed vocabularies are `Literal` types: `race.status == "resulted"` is a type
error because the public word is `"final"`.

## Common tasks

### Today's races

```python
races = client.events.list(sport="thoroughbred", country="au", limit=20)
for race in races:
    print(race.start_at, race.name, race.status)

open_now = client.events.list(sport=["thoroughbred", "greyhound"], status=["open", "in_progress"])
```

With no time window you get races from a few minutes ago onwards. Pass
`start_from=` / `start_to=` for history or a later day.

### Prices for one race

```python
card = client.events.snapshot(race.id)

runner = card.entrants[0]
card.best_price(runner)              # highest win price across sources
card.price(runner, "sportsbet")      # one source
card.quotes(runner, market="place")  # every priced place quote
```

Scratched runners carry `runner.racing.scratched_at` and the late-scratching
`runner.racing.deduction`. Exchange quotes carry `quote.exchange` with back and
lay ladders and the Betfair `market_id` / `selection_id`.

Add `include="history"` to `client.odds.list(event=race.id, include="history")`
for each source's price fluctuations.

### Live prices

Take a snapshot, then follow it. The snapshot carries the exact stream position
it was read at, so nothing that changes in between is missed:

```python
from betwatch import OddsFrame

card = client.events.snapshot(race.id)
with client.follow(card) as live:
    for frame in live:
        if isinstance(frame, OddsFrame):
            print(frame.data.source.id, frame.data.entrant_id, frame.data.price)
```

To keep the card itself current, apply each frame to it.
`card.apply(frame)` returns True only when something actually changed:

```python
with client.follow(card) as live:
    for frame in live:
        if card.apply(frame):
            print(card.best_price(card.entrants[0]))
```

`client.watch(race.id)` does the snapshot and the follow in one call, and takes
a fresh snapshot by itself if the server ever asks for one.

### A whole raceday on one connection

Stream frames are not metered, so one filtered stream is both the cheapest and
the fastest way to stay current. Polling costs quota on every call.

```python
from betwatch import RacingScope

scope = RacingScope(sport="thoroughbred", country="au", key="win")
snap = client.snapshot(scope, limit=10)    # first page of races, plus their prices
with client.follow(snap) as live:          # live within seconds
    page = snap
    while page.next:                       # read the rest of the day while streaming
        page = client.snapshot_page(after=page.next)
    for frame in live:
        ...
```

Every page shares the first page's stream position, so races you read later
still replay anything that changed while you were reading them.

### Resume after a restart

Persist the stream's continuation and follow it again later. It carries the
position and the filters that produced it:

```python
from pathlib import Path
from betwatch import StreamContinuation

Path("position.json").write_bytes(live.continuation.to_json())

position = StreamContinuation.from_json(Path("position.json").read_bytes())
with client.follow(position) as live:
    ...
```

If the position is too old to resume, the stream raises `ResyncRequired`; take
a new snapshot and follow that.

### Every page of a collection

```python
for venue in client.venues.iter(country="au"):
    print(venue.name)
```

`list()` returns one page; `iter()` follows every page for you.

### pandas

```python
import pandas as pd

df = pd.DataFrame.from_records(card.to_records())  # one row per quote, with runner names
```

### Async

`AsyncBetwatch` has the same methods, awaited:

```python
from betwatch import AsyncBetwatch

async with AsyncBetwatch() as client:
    card = await client.events.snapshot(race_id)
    async with client.watch(race_id) as live:
        async for frame in live:
            ...
```

## Errors, retries and limits

Every API error raises a typed exception carrying the problem's stable `code`,
a human `detail`, and the `request_id` / `trace_id` to quote to support:

```python
import time
from betwatch import NotFoundError, QuotaExceededError, RateLimitError

try:
    card = client.events.snapshot(race_id)
except RateLimitError as err:            # per-minute window; worth waiting out
    time.sleep(err.retry_after or 1)
except QuotaExceededError as err:        # monthly quota; resets in days, not seconds
    print("quota resets", err.rate_limit.monthly_reset)
except NotFoundError:
    ...
```

- The client retries rate limits and transient server errors twice by default
  (`Betwatch(max_retries=...)`) and never retries an error that cannot succeed.
- Streams reconnect by themselves after a dropped connection, from the last
  frame they delivered.
- `client.rate_limit` shows the per-minute and monthly budget from the last
  response.
- Too many concurrent streams raises `StreamLimitError`; a key used from an IP
  outside its allow-list raises `IPNotAllowedError`.

## Upgrades

The API only grows. New fields are ignored, new stream frame types arrive as
`UnknownFrame`, and a new vocabulary value (a new sport, odds state, or source
kind) decodes as `"unknown"` instead of failing, so an older SDK keeps working
against a newer API.

## Benchmarks

`2.0.0b4` against the `1.x` GraphQL client (`betwatch==1.7.4`), measured with
the published SDK code on 28 October 2026. Both clients ran on the same
machine at the same time with production keys.

### Live odds

Both SDKs streamed every race for 15 minutes (21:11–21:26 AEDT, evening
thoroughbred, harness and greyhound meetings): `client.follow()` on one
connection for 2.x, and `subscribe_bookmaker_updates("")` for 1.x. Each price
was timestamped when the SDK handed it to user code. A move is one
bookmaker's win price on one runner changing from one value to another. A move
was paired when it happened exactly once on each stream within two minutes.

How far ahead 2.x delivered the same price move, by time to the advertised
jump:

| Time to jump | Moves | Average ahead | Median ahead |
|---|---:|---:|---:|
| 30+ min | 57 | 19.2 s | 11.1 s |
| 10–30 min | 242 | 13.3 s | 7.2 s |
| 5–10 min | 957 | 12.1 s | 9.1 s |
| 2–5 min | 1,910 | 9.3 s | 7.2 s |
| 0–2 min | 1,044 | 10.5 s | 7.8 s |
| Past advertised start | 510 | 12.6 s | 7.9 s |
| **All** | **4,720** | **10.8 s** | **7.9 s** |

"Ahead" is signed: the averages include the moves where 1.x was first.

| Over the same 15 minutes | 1.x | 2.x |
|---|---:|---:|
| Win-price changes on the same 55 races and 46 bookmakers | 9,299 | 13,005 |
| Price updates delivered, all races | 33,722 (win only) | 72,454 (win, place and early markets) |
| Sources | 53 | 76 |
| Connections | 1 websocket | 1 SSE stream |

### Library and key paths

| Path | 1.x | 2.x |
|---|---:|---:|
| `import betwatch` | 235 ms | 87 ms |
| Installed dependencies | 22 packages, 16 MB | 9 packages, 2.6 MB |
| Today's races, no prices (p50 of 5) | 4.17 s for 416 races | 1.03 s for 215 races |
| One race card with every price (p50 / p95 of 30) | 0.72 s / 1.88 s, 367 prices | 0.44 s / 0.75 s, 1,064 prices |
| Decode one race card, JSON bytes to typed objects | 3.96 ms (85 KB) | 0.72 ms (394 KB) |
| Decode the 15 minute live stream above | 31.6 µs per price | 5.1 µs per price |
| Live stream decode rate, one core | 32,000 prices/s | 196,000 prices/s |

- **Race card:** `client.get_race(id, RaceProjection(markets=True,
  place_markets=True, betfair=True))` against `client.events.snapshot(id)`, on
  the next 10 races to jump, three times each.
- **Decode:** the best of several replays of the payloads each SDK received
  above. 1.x is `json.loads` plus `typedload`. 2.x is the SSE parser plus
  [msgspec](https://jcristharif.com/msgspec/) structs.
- **Network:** request times include the network from a client in Oregon, US.
  Both APIs are behind the same CDN edge, so both pay the same round trip.
  From Australia they are lower.

## More

- [Racing API documentation](https://beta.betwatch.com/docs/api/): streaming,
  limits, errors and every endpoint.
- [Examples](examples): races, race prices, live subscriptions, a whole-day
  firehose, and a terminal raceday grid (`examples/tui.py`).
- [Changelog](CHANGELOG.md)
- Issues: [github.com/betwatch/betwatch-sdk-python/issues](https://github.com/betwatch/betwatch-sdk-python/issues)

Working on the SDK itself? See [CONTRIBUTING.md](CONTRIBUTING.md).

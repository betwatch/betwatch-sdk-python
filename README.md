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

## Performance

Responses decode straight into typed structs with
[msgspec](https://jcristharif.com/msgspec/). On recorded beta traffic a
100-race snapshot (17 MB, 43,000 prices) decodes in about 50 ms, and a live
stream decodes at about 175,000 frames per second on one core.

## More

- [Racing API documentation](https://beta.betwatch.com/docs/api/): streaming,
  limits, errors and every endpoint.
- [Examples](examples): races, race prices, live subscriptions, a whole-day
  firehose, and a terminal raceday grid (`examples/tui.py`).
- [Changelog](CHANGELOG.md)
- Issues: [github.com/betwatch/betwatch-sdk-python/issues](https://github.com/betwatch/betwatch-sdk-python/issues)

Working on the SDK itself? See [CONTRIBUTING.md](CONTRIBUTING.md).

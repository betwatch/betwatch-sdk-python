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

```python
from betwatch import Betwatch, OddsFrame

with Betwatch() as client:
    page = client.events.list(sport="thoroughbred", country="au", limit=5)
    event = page[0]
    print(event.name, event.start_at, event.racing.race_number)

    with client.watch(event.id) as live:
        print(live.snapshot.event.name, "runners", len(live.snapshot.entrants))
        for frame in live:
            if isinstance(frame, OddsFrame):
                print(frame.data.source.id, frame.data.price)
```

Dump to pandas without caring that the backend is msgspec:

```python
import pandas as pd

card = client.events.snapshot(event.id)
df = pd.DataFrame.from_records(card.to_records())
```

Sync and async clients share one resource tree (`AsyncBetwatch`).

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

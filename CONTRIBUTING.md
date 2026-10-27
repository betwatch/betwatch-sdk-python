# Contributing

## Setup and gates

```console
uv sync --all-groups
bash tools/check.sh      # lockfile, format, lint, ty, pyright, tests: what CI runs
```

Agents: read [`AGENTS.md`](AGENTS.md) first.

## Credentials

Secrets live in a gitignored `fnox.toml`, encrypted to this machine's age key
(`~/.config/fnox/age.txt`). Ciphertext is not committed.

```console
fnox exec -- uv run examples/live_check.py                  # local API, http://127.0.0.1:8888
fnox exec --profile prod -- uv run examples/watch_event.py  # hosted beta
```

Or set `BETWATCH_API_KEY` and `BETWATCH_API_URL` yourself.

## The contract

Error codes, budget-header names and operation coverage are pinned against a
committed copy of the published contract at `tests/contract/openapi.json`.
When the API ships a new spec:

```console
uv run tests/contract/sync_openapi.py     # or: BETWATCH_OPENAPI=/path/to/openapi.json
uv run pytest tests/test_contract_spec.py
```

A failure there names exactly what moved: a new error code with no retry
decision, a budget header nothing parses, an operation with no method.

Operation ids map one-to-one onto resource methods:

| operationId | SDK |
|---|---|
| `listEvents` / `getEvent` / `getEventSnapshot` | `client.events.list` / `.retrieve` / `.snapshot` |
| `getSnapshot` | `client.snapshot` / `.snapshot_page` |
| `listEntrants` / `getEntrant` | `client.entrants.list` / `.retrieve` |
| `getCompetitor` | `client.competitors.retrieve` |
| `listOdds` / `getOdds` | `client.odds.list` / `.retrieve` |
| `listMeetings` / `getMeeting` | `client.meetings.list` / `.retrieve` |
| `listVenues` / `getVenue` | `client.venues.list` / `.retrieve` |
| `listSources` | `client.sources.list` |
| `streamRacing` | `client.stream` / `.watch` / `.follow` |

## Measuring the stream

`tools/stream_timing.py` reports how long `/v2/stream` takes to bootstrap for a
scope: time to `ready`, time to the first data frame, the silence between them,
and time to `sync`. `--require-sync N` exits non-zero past N seconds, so it
works as a regression gate.

```console
fnox exec --profile prod -- uv run tools/stream_timing.py --sport thoroughbred --country au
```

## Terminal grid

`examples/tui.py` is a Textual demo, not part of the installed package: races
ordered by time to jump on the left, runner × source prices on the right,
following `/v2/stream` live.

```console
fnox exec -- uv run examples/tui.py --sport harness --country au
```

`1`/`2`/`3` switch code, `n` jumps to the next race, `w`/`p` is win/place,
`/` filters tracks, `?` is help.

## Releasing

From a clean `beta`:

```console
tools/release.sh 2.0.0b4
git push origin HEAD v2.0.0b4
```

The script bumps `src/betwatch/__about__.py`, prepends `CHANGELOG.md` from
conventional commits with git-cliff, runs every gate, commits and tags. The tag
runs `.github/workflows/release.yml`, which refuses a tag without a changelog
section, publishes with PyPI Trusted Publishing, and creates the GitHub
release with the same notes (a pre-release for a/b/rc versions). Commit
subjects become the changelog, so write them for a reader:
`feat(stream): …`, `fix: …`, `perf: …`.

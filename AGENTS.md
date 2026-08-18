# Betwatch Python SDK — agent guide

This is the **public `/v1` REST + SSE** client (`2.0.0b1` on branch `beta`).
It is **not** the GraphQL 1.x SDK. There is no `get_races`.

## Load this first

- Events are races. Entrants are runners. Odds are one source's price on one outcome.
- Session `/racing/*` is a private frontend BFF. Never call it from this package.
- Auth: header `X-API-Key`. Env: `BETWATCH_API_KEY`. Optional `BETWATCH_API_URL`.
- Load them with fnox, do not paste keys into the shell:
  `fnox exec -- <cmd>` (local, `http://127.0.0.1:8888`) or
  `fnox exec --profile prod -- <cmd>` (hosted `https://api-beta.betwatch.com`).
- `fnox.toml` is gitignored, including ciphertext. It is encrypted to the
  machine age identity at `~/.config/fnox/age.txt`.
- Default host if unset is `https://api-beta.betwatch.com`.

Copy-paste examples match 1.x use cases: `examples/get_races.py`,
`examples/get_race_prices.py`, `examples/subscriptions.py`.
`examples/tui.py` is a Textual raceday grid — example only, not installed.

## Do this, in this order

```python
from betwatch import Betwatch, OddsFrame

with Betwatch() as client:
    races = client.events.list(sport="thoroughbred", country="au", limit=10)
    race = races.next_open or races[0]
    card = client.events.snapshot(race.id)
    print(card.best_price(card.entrants[0]), card.price(card.entrants[0], "sportsbet"))
    with client.watch(race.id) as live:
        for frame in live:
            if isinstance(frame, OddsFrame):
                print(frame.data.source.id, frame.data.price)
```

If `ResyncRequired` is raised: **do not** reconnect with the old cursor. Call
`client.watch(event_id)` again (it re-snapshots).

## Surfaces

| Want | Call |
|---|---|
| Today's races | `client.events.list(sport="thoroughbred", country="au")` (default window is now) |
| Open races only | `client.events.list(..., status="open")` or `status=["open", "in_progress"]` |
| Next open race | `races.next_open` |
| One race card + prices | `client.events.snapshot(event_id)` then `card.quotes(runner)` / `card.best_price(runner)` / `card.price(runner, "sportsbet")` |
| Live updates | `client.watch(event_id)` or `client.follow(snapshot)` |
| Pandas | `page.to_records()` / `snapshot.to_records()` then `DataFrame.from_records` |
| Terminal grid | `fnox exec -- uv run examples/tui.py` (example only, not shipped) |

Filters accept a string or a list: `sport="thoroughbred"` is fine.
Status, sport, and other closed vocabularies are Literals. Compare with
`"open"` or `EventStatuses.OPEN`. `"resulted"` is not a public status
(`final` is). `has_status("resulted")` fails `ty`; `status == "resulted"`
fails `pyright` (`reportUnnecessaryComparison`).

## Do not

- Do not invent nested paths (`/v1/events/{id}/odds`). They were deleted.
- Do not pass `**params`. Every argument is an explicit keyword.
- Do not use GraphQL, WebSockets, or `include=card`.
- Do not treat `ping` frames as data — the SDK swallows them and still advances the cursor.
- Do not publish from `main` as `2.0.0` until this contract is promoted.

## Starting a stream

Bootstrap over REST, then follow the cursor it returns. One shape, any scope:

```python
snap = client.snapshot(sport="thoroughbred", country="au")  # card + prices + cursor
with client.follow(snap) as live:
    ...
```

`client.watch(event_id)` is the same thing for a single race. Every snapshot
page returns the same `stream.cursor`, so follow from any page and page the
rest with `after=snap.next`.

`snapshot="full"` on the stream is only accepted for an event, meeting or
venue; anything broader is `422 filter_required` pointing at `/v1/snapshot`.
Do not reach for it — `follow()` sends `snapshot="none"` and the cursor, which
is what you want.

A `resync` is routine — an ingestion worker restarting broadcasts one to every
client — so re-bootstrap cheaply and do not treat it as exceptional.

## Out of the box

Reach for the SDK before writing it in an example. `client.stream(progress=
print_progress)` reports a `snapshot=full` bootstrap, which otherwise looks
hung for 20-45s. `ChangeTracker().changed(frame_or_odds_row)` drops
republished state that has not moved. `tools/stream_timing.py` measures a
scope's bootstrap. Examples demonstrate the client; they do not reimplement it.

## Errors

Every failure is an RFC 9457 problem document. **Branch on `.code`, never on
`.title` or `.detail`** — `ErrorCodes` has the vocabulary. The exception type is
selected from the code, falling back to the HTTP class for a code this release
has never seen. Read `.code`, `.detail`, `.errors`, `.request_id`, `.trace_id`.

`AuthenticationError` (401) · `PermissionDeniedError` (403) with subclasses
`EntitlementEmptyError` and `AccountDisabledError` · `NotFoundError` (404) ·
`MethodNotAllowedError` (405) · `UnsupportedMediaTypeError` (406/415) ·
`UnprocessableEntityError` (422) · `RateLimitError` (429 `rate_limited`) ·
`QuotaExceededError` (429 `quota_exceeded`) · `StreamLimitError` (429
`stream_limit`) · `ServiceUnavailableError` (503) · `InternalServerError` (5xx).
Local, before any HTTP: `FilterRequiredError`, `CredentialInQueryError`.
Stream recovery: `ResyncRequired`.

`QuotaExceededError` and `StreamLimitError` are **not** subclasses of
`RateLimitError`. All three are 429 and only one is worth waiting out, so
`except RateLimitError` must not catch the other two.

Retries follow the code, not the status: `rate_limited` (after `Retry-After`),
`quota_unavailable`, `stream_unavailable`, `unavailable`, `internal_error`.
Everything else fails fast. `cursor_expired` / `cursor_scope_changed` (409) mean
re-bootstrap over REST, not retry.

## Paging

Every collection has `iter()` alongside `list()`. A cursor belongs to the
collection that issued it — `iter()` feeds each one back to the same endpoint,
which is the only thing that makes this safe. Never move a `next` between
endpoints, and never decode, build, or edit a cursor.

## Forward compatibility

The contract only grows, so nothing here may fail on something new. Unknown
response fields (including `$schema`) are ignored, unknown SSE frame names
become `UnknownFrame`, and an unrecognised vocabulary value decodes as
`"unknown"` (see `_compat.py`). Do not add `forbid_unknown_fields` to a model,
and when widening a response vocabulary keep its `"unknown"` member.

## Public nouns

`evt_` event · `ent_` entrant · `cmp_` competitor · `mtg_` meeting · `ven_` venue ·
`mkt_` market · `out_` outcome · `odd_` odds

Stored ids (`evt_`, `ent_`, `cmp_`, `mtg_`, `ven_`) survive an entity merge: the
server resolves them to the surviving record and returns it as 200, never a
redirect. Derived ids (`mkt_`, `out_`, `odd_`) do not — they embed their owning
event, so after a merge the same market has a different id and the old one 404s.

That is not data loss. Re-read the event and take the new ids. A `NotFoundError`
on a derived id held across a merge is the expected answer, not a bug.

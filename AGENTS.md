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

## Errors

Typed exceptions: `NotFoundError` (404), `AuthenticationError` (401),
`PermissionDeniedError` (403 — missing `stream` scope), `UnprocessableEntityError`
(422), `RateLimitError` (429), `FilterRequiredError` (local, no HTTP),
`ResyncRequired` (stream recovery). Read `.detail` and `.code` on HTTP errors.

## Public nouns

`evt_` event · `ent_` entrant · `cmp_` competitor · `mtg_` meeting · `ven_` venue ·
`mkt_` market · `out_` outcome · `odd_` odds

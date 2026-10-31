from __future__ import annotations

from datetime import UTC, datetime

import msgspec

from betwatch import Event, EventSnapshot, to_dict, to_json, to_records
from betwatch.types.event import EventPage


def test_event_round_trips_camel_json_and_dumps_for_pandas() -> None:
    raw = (
        b'{"id":"evt_1","sport":"thoroughbred","name":"R1","startAt":"2026-08-14T04:00:00Z",'
        b'"status":"open","venueId":"ven_1","meetingId":"mtg_1","racing":{"raceNumber":1},'
        b'"updatedAt":"2026-08-14T03:00:00Z"}'
    )
    event = msgspec.json.decode(raw, type=Event)
    assert event.id == "evt_1"
    assert event.start_at == datetime(2026, 8, 14, 4, 0, tzinfo=UTC)
    assert event.racing.race_number == 1
    dumped = event.to_dict()
    assert dumped["id"] == "evt_1"
    assert dumped["venueId"] == "ven_1"
    records = to_records([event])
    assert records[0]["id"] == "evt_1"
    assert b'"evt_1"' in to_json(event)
    assert to_dict(event)["name"] == "R1"


def test_snapshot_and_page_decode_nested_collections() -> None:
    raw = (
        b'{"stream":{"cursor":"cur_1","event":["evt_1"],"source":[]},"event":{"id":"evt_1","sport":"thoroughbred","name":"R1",'
        b'"startAt":"2026-08-14T04:00:00Z","status":"open","racing":{"raceNumber":1}},'
        b'"entrants":[{"id":"ent_1","eventId":"evt_1","competitorId":"cmp_1","name":"A",'
        b'"entryState":"listed","racing":{"number":1}}],'
        b'"odds":[],"coverage":[]}'
    )
    card = msgspec.json.decode(raw, type=EventSnapshot)
    assert card.stream is not None
    assert card.stream.cursor == "cur_1"
    assert card.event.id == "evt_1"
    assert card.entrants[0].competitor_id == "cmp_1"
    assert card.entrants[0].racing.number == 1
    assert to_records(card.entrants)[0]["eventId"] == "evt_1"

    page = msgspec.json.decode(
        b'{"items":[{"id":"evt_1","sport":"thoroughbred","name":"R1",'
        b'"startAt":"2026-08-14T04:00:00Z","status":"open","racing":{}}],"next":"lst_2"}',
        type=EventPage,
    )
    assert len(page) == 1
    assert page[0].id == "evt_1"
    assert [item.id for item in page] == ["evt_1"]
    assert page.next == "lst_2"
    assert page[0].is_open
    assert page.next_open is page[0]
    from betwatch import EventStatuses

    assert page[0].status == EventStatuses.OPEN
    assert page[0].status != EventStatuses.FINAL


def test_unknown_status_is_rejected_at_decode() -> None:
    import pytest

    with pytest.raises(msgspec.ValidationError):
        msgspec.json.decode(
            b'{"id":"evt_1","sport":"thoroughbred","name":"R1",'
            b'"startAt":"2026-08-14T04:00:00Z","status":"resulted","racing":{}}',
            type=Event,
        )


def test_pyright_rejects_impossible_status_eq() -> None:
    import subprocess
    from pathlib import Path

    root = Path(__file__).resolve().parents[1]
    ok = subprocess.run(
        ["uv", "run", "pyright", "tests/typing/status_eq_ok.py"],
        cwd=root,
        capture_output=True,
        text=True,
        check=False,
    )
    assert ok.returncode == 0, ok.stdout + ok.stderr
    bad = subprocess.run(
        ["uv", "run", "pyright", "tests/typing/status_eq_bad.py"],
        cwd=root,
        capture_output=True,
        text=True,
        check=False,
    )
    assert bad.returncode != 0, "pyright must reject event.status == 'resulted'"
    combined = bad.stdout + bad.stderr
    assert "resulted" in combined.lower() or "overlap" in combined.lower()


def test_ty_rejects_impossible_status_compare() -> None:
    import subprocess
    from pathlib import Path

    root = Path(__file__).resolve().parents[1]
    ok = subprocess.run(
        ["uv", "run", "ty", "check", "tests/typing/status_ok.py"],
        cwd=root,
        capture_output=True,
        text=True,
        check=False,
    )
    assert ok.returncode == 0, ok.stdout + ok.stderr
    bad = subprocess.run(
        ["uv", "run", "ty", "check", "tests/typing/status_bad.py"],
        cwd=root,
        capture_output=True,
        text=True,
        check=False,
    )
    assert bad.returncode != 0, "ty must reject event.status == 'resulted'"
    combined = bad.stdout + bad.stderr
    assert (
        "resulted" in combined.lower()
        or "literal" in combined.lower()
        or "invalid" in combined.lower()
    )


def test_scope_filters_are_strict_on_requests() -> None:
    import subprocess
    from pathlib import Path

    root = Path(__file__).resolve().parents[1]
    for checker in (["uv", "run", "pyright"], ["uv", "run", "ty", "check"]):
        ok = subprocess.run(
            [*checker, "tests/typing/scope_ok.py"],
            cwd=root,
            capture_output=True,
            text=True,
            check=False,
        )
        assert ok.returncode == 0, ok.stdout + ok.stderr
        bad = subprocess.run(
            [*checker, "tests/typing/scope_bad.py"],
            cwd=root,
            capture_output=True,
            text=True,
            check=False,
        )
        assert bad.returncode != 0, "request filters must reject response-only unknown values"


def test_empty_collections_decode_as_empty_lists() -> None:
    """The contract guarantees `[]` rather than null, so the models take it plainly.

    This used to arrive as null and be rewritten by a walk over every payload.
    `test_contract_spec.py` pins the guarantee at its source.
    """
    from betwatch._base_client import decode_model

    raw = (
        b'{"stream":{"cursor":"cur_1","event":["evt_1"],"source":[]},'
        b'"event":{"id":"evt_1","sport":"thoroughbred","name":"R1",'
        b'"startAt":"2026-08-14T04:00:00Z","status":"open","racing":{}},'
        b'"entrants":[],"odds":[],"coverage":[]}'
    )
    card = decode_model("/v2/events/evt_1/snapshot", raw, EventSnapshot)
    assert card.entrants == []
    assert card.odds == []


def test_snapshot_price_helpers() -> None:
    card = msgspec.json.decode(
        b'{"stream":{"cursor":"cur_1","event":["evt_1"],"source":[]},'
        b'"event":{"id":"evt_1","sport":"thoroughbred","name":"R1",'
        b'"startAt":"2026-08-14T04:00:00Z","status":"open","racing":{}},'
        b'"entrants":[{"id":"ent_1","eventId":"evt_1","competitorId":"cmp_1","name":"A",'
        b'"entryState":"listed","racing":{"number":4}}],'
        b'"odds":[{"id":"odd_1","eventId":"evt_1","key":"win",'
        b'"source":{"id":"sportsbet","name":"Sportsbet","kind":"bookmaker"},'
        b'"state":"available","price":3.2,"entrantId":"ent_1"},'
        b'{"id":"odd_2","eventId":"evt_1","key":"win",'
        b'"source":{"id":"tab","name":"TAB Fixed","kind":"bookmaker"},'
        b'"state":"available","price":2.8,"entrantId":"ent_1"}],'
        b'"coverage":[]}',
        type=EventSnapshot,
    )
    runner = card.entrants[0]
    assert runner.number == 4
    assert card.best_price(runner) == 3.2
    assert card.lowest_price(runner) == 2.8
    assert card.price(runner, "sportsbet") == 3.2
    assert len(card.quotes(runner)) == 2


def test_contract_2_1_racing_and_exchange_fields_decode() -> None:
    """Scratching, gear and Betfair ids arrive as typed fields, not dropped keys."""
    from betwatch._base_client import decode_model
    from betwatch.types.entrant import Entrant
    from betwatch.types.odds import Odds

    entrant = decode_model(
        "/v2/entrants/ent_1",
        b'{"id":"ent_1","eventId":"evt_1","competitorId":"cmp_1","name":"A",'
        b'"entryState":"listed","scratched":true,"racing":{"number":3,"emergency":true,'
        b'"blinkers":true,"gear":"Blinkers first time","riderClaimKg":1.5,'
        b'"scratchedAt":"2026-08-14T03:00:00Z",'
        b'"deduction":{"kind":"range","winMin":5,"winMax":8}}}',
        Entrant,
    )
    racing = entrant.racing
    assert racing.emergency is True and racing.blinkers is True
    assert racing.rider_claim_kg == 1.5
    assert racing.scratched_at == datetime(2026, 8, 14, 3, 0, tzinfo=UTC)
    assert racing.deduction is not None
    assert (racing.deduction.kind, racing.deduction.win_min, racing.deduction.win_max) == (
        "range",
        5,
        8,
    )
    assert racing.deduction.win_cents is None

    newer = decode_model(
        "/v2/entrants/ent_1",
        b'{"id":"ent_1","eventId":"evt_1","competitorId":"cmp_1","name":"A",'
        b'"entryState":"listed","racing":{"deduction":{"kind":"provisional"}}}',
        Entrant,
    )
    assert newer.racing.deduction is not None and newer.racing.deduction.kind == "unknown"

    odds = decode_model(
        "/v2/odds/odd_1.a",
        b'{"id":"odd_1.a","eventId":"evt_1","key":"win",'
        b'"source":{"id":"betfair","name":"Betfair","kind":"exchange"},"state":"available",'
        b'"exchange":{"marketState":"open","outcomeState":"active","marketId":"1.234",'
        b'"selectionId":5678,"back":[{"price":3.1,"size":120.5}]}}',
        Odds,
    )
    assert odds.exchange is not None
    assert (odds.exchange.market_id, odds.exchange.selection_id) == ("1.234", 5678)
    assert odds.exchange.back[0].size == 120.5


def test_event_snapshot_apply_upserts_live_frames() -> None:
    from betwatch.types.stream import frame_for_event

    def odds(id: str, price: float, event: str = "evt_1") -> bytes:
        return msgspec.json.encode(
            {
                "id": id,
                "eventId": event,
                "key": "win",
                "entrantId": "ent_1",
                "source": {"id": id, "name": id, "kind": "bookmaker"},
                "state": "available",
                "price": price,
            }
        )

    card = msgspec.json.decode(
        b'{"stream":{"cursor":"c"},"event":{"id":"evt_1","sport":"thoroughbred","name":"R1",'
        b'"startAt":"2026-08-14T04:00:00Z","status":"open"},'
        b'"entrants":[{"id":"ent_1","eventId":"evt_1","competitorId":"c","name":"A",'
        b'"entryState":"listed"}],"odds":[' + odds("sb", 3.0) + b"," + odds("tab", 2.5) + b"]}",
        type=EventSnapshot,
    )
    assert card.apply(frame_for_event("odds", "c1", odds("tab", 4.0))) is True
    assert card.apply(frame_for_event("odds", "c2", odds("tab", 4.0))) is False, "republish"
    assert card.apply(frame_for_event("odds", "c3", odds("bf", 5.0))) is True
    assert card.apply(frame_for_event("odds", "c4", odds("x", 9.0, event="evt_2"))) is False
    assert [(q.source.id, q.price) for q in card.odds] == [("sb", 3.0), ("tab", 4.0), ("bf", 5.0)]
    assert card.best_price("ent_1") == 5.0

    card.odds.pop(0)  # edited behind apply's back: the index must not go stale
    assert card.apply(frame_for_event("odds", "c5", odds("bf", 6.0))) is True
    assert [(q.source.id, q.price) for q in card.odds] == [("tab", 4.0), ("bf", 6.0)]

    closed = msgspec.json.encode({"id": "evt_1", "status": "closed"})
    assert card.apply(frame_for_event("event", "c6", closed)) is True
    assert card.event.status == "closed" and card.event.name == "R1"
    assert b'"odds"' in card.to_json() and b"__dict__" not in card.to_json()


def test_contract_2_2_book_and_stream_url_decode() -> None:
    """Coverage books and the follow URL arrive typed, on REST and SSE."""
    from betwatch import ChangeTracker, CoverageBookStatuses, ScopeSnapshot
    from betwatch._base_client import decode_model
    from betwatch.types.stream import CoverageFrame, frame_for_event

    def coverage(status: str, priced: int, *, full: bool = False) -> bytes:
        book: dict[str, object] = {"status": status, "active": 2, "priced": priced}
        if full:
            book["fullAt"] = "2026-10-30T01:00:00Z"
            book["firstFull"] = [
                {"entrantId": "ent_1", "price": 2.4, "observedAt": "2026-10-30T00:59:58Z"},
                {"entrantId": "ent_2", "price": 5.5, "observedAt": "2026-10-30T01:00:00Z"},
            ]
        return msgspec.json.encode(
            {
                "eventId": "evt_1",
                "key": "win",
                "sourceId": "sportsbet",
                "state": "priced",
                "observedAt": "2026-10-30T01:00:00Z",
                "book": book,
            }
        )

    snap = decode_model(
        "/v2/events/snapshot",
        b'{"stream":{"cursor":"cur_1","event":[],"source":["sportsbet"],"sport":["greyhound"],'
        b'"url":"/v2/stream?cursor=cur_1&snapshot=none&source=sportsbet&sport=greyhound"},'
        b'"events":[],"entrants":[],"odds":[{"id":"odd_1.a","eventId":"evt_1","key":"win",'
        b'"entrantId":"ent_1","source":{"id":"sportsbet","name":"Sportsbet","kind":"bookmaker"},'
        b'"state":"available","price":2.6}],'
        b'"coverage":[' + coverage("full", 2, full=True) + b"]}",
        ScopeSnapshot,
    )
    assert (
        snap.stream.url == "/v2/stream?cursor=cur_1&snapshot=none&source=sportsbet&sport=greyhound"
    )
    book = snap.coverage[0].book
    assert book is not None and book.status == CoverageBookStatuses.FULL
    assert (book.active, book.priced) == (2, 2)
    assert book.full_at == datetime(2026, 10, 30, 1, 0, tzinfo=UTC)
    assert book.first_full is not None
    assert [(p.entrant_id, p.price) for p in book.first_full] == [("ent_1", 2.4), ("ent_2", 5.5)]
    assert to_records(snap.coverage)[0]["book"]["firstFull"][1]["entrantId"] == "ent_2"

    # Book is optional, and a status newer than the SDK reads as "unknown".
    bare = frame_for_event(
        "coverage", "c0", coverage("partial", 1).replace(b',"book":{', b',"x":{')
    )
    assert isinstance(bare, CoverageFrame) and bare.data.book is None
    newer = frame_for_event("coverage", "c0", coverage("overpriced", 1))
    assert isinstance(newer, CoverageFrame) and newer.data.book is not None
    assert newer.data.book.status == "unknown"

    # A book that moves is a change even when state does not.
    tracker = ChangeTracker()
    assert tracker.changed(frame_for_event("coverage", "c1", coverage("partial", 1))) is True
    assert tracker.changed(frame_for_event("coverage", "c2", coverage("partial", 1))) is False
    assert tracker.changed(frame_for_event("coverage", "c3", coverage("full", 2, full=True)))

    card = msgspec.json.decode(
        b'{"stream":{"cursor":"c"},"event":{"id":"evt_1","sport":"greyhound","name":"R1",'
        b'"startAt":"2026-10-30T04:00:00Z","status":"open"},"coverage":['
        + coverage("partial", 1)
        + b"]}",
        type=EventSnapshot,
    )
    assert card.apply(frame_for_event("coverage", "c4", coverage("partial", 1))) is False
    assert card.apply(frame_for_event("coverage", "c5", coverage("full", 2, full=True))) is True
    assert card.coverage[0].book is not None and card.coverage[0].book.status == "full"


def test_current_price_helpers_exclude_unconfirmed_and_unavailable_quotes() -> None:
    event = Event(
        id="evt_1", sport="harness", name="R10", start_at=datetime.now(UTC), status="open"
    )
    rows: list[dict[str, object]] = [
        {"id": "fresh", "price": 4, "state": "available", "confirmation": "confirmed"},
        {"id": "unconfirmed", "price": 21, "state": "available", "confirmation": "unconfirmed"},
        {"id": "suspended", "price": 16, "state": "suspended", "confirmation": "confirmed"},
        {"id": "legacy", "price": 3, "state": "available"},
    ]
    for row in rows:
        row.update(
            eventId="evt_1",
            entrantId="ent_1",
            key="win",
            source={"id": str(row["id"]), "name": str(row["id"]), "kind": "bookmaker"},
        )
    card = msgspec.json.decode(
        msgspec.json.encode({"event": event, "odds": rows}), type=EventSnapshot
    )
    assert card.best_price("ent_1") == 4
    assert card.lowest_price("ent_1") == 3
    assert card.price("ent_1", "unconfirmed") is None
    assert [quote.id for quote in card.quotes("ent_1")] == ["fresh", "legacy"]


def test_compact_snapshot_and_form_preserve_unknown_facts() -> None:
    import pytest

    from betwatch import Betwatch, CompetitorForm

    body = {
        "event": {
            "id": "evt_1",
            "sport": "harness",
            "name": "R10",
            "startAt": "2026-10-30T11:37:00Z",
            "status": "open",
        },
        "maxAge": 120,
        "summary": [
            {
                "entrantId": "ent_1",
                "name": "Chillax",
                "number": 3,
                "prices": [
                    {
                        "key": "win",
                        "sourceKind": "bookmaker",
                        "best": 4,
                        "median": 3.5,
                        "sourceCount": 2,
                        "latestCheckedAt": "2026-10-30T11:35:58Z",
                        "oldestCheckedAt": "2026-10-30T11:35:00Z",
                    }
                ],
            }
        ],
    }
    card = msgspec.json.decode(msgspec.json.encode(body), type=EventSnapshot)
    assert card.stream is None and card.odds == [] and card.max_age == 120
    assert card.summary[0].prices[0].median == 3.5
    with Betwatch(api_key="test") as client:
        with pytest.raises(ValueError, match="no stream handoff"):
            client.follow(card)
    form = msgspec.json.decode(
        b'{"items":[{"eventId":"evt_1","entrantId":"ent_1","startAt":"2026-10-29T11:00:00Z",'
        b'"raceNumber":9,"number":3,"finish":null,"fieldSize":8,"distanceMeters":null,'
        b'"startingPrice":null,"winningMargin":null}]}',
        type=CompetitorForm,
    )
    assert form[0].finish is None and form[0].distance_meters is None
    assert form[0].field_size == 8 and form[0].starting_price is None


def test_source_region_tells_same_brand_books_apart() -> None:
    from betwatch.types.source import SourcePage

    raw = (
        b'{"items":['
        b'{"id":"ladbrokes","name":"Ladbrokes","kind":"bookmaker","region":"au"},'
        b'{"id":"ladbrokes-gb","name":"Ladbrokes","kind":"bookmaker","region":"gb"},'
        # A region added after this release still decodes.
        b'{"id":"fanduel","name":"FanDuel","kind":"bookmaker","region":"us"},'
        b'{"id":"betfair","name":"Betfair","kind":"exchange"}]}'
    )
    page = msgspec.json.decode(raw, type=SourcePage)
    assert [s.region for s in page.items] == ["au", "gb", "us", None]

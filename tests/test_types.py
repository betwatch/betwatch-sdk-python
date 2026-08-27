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

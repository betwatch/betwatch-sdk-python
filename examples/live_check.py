#!/usr/bin/env python3
"""Import the shipped SDK twice and hit local /v2 list + snapshot + stream."""

from __future__ import annotations

import os
import sys
from datetime import UTC, datetime, timedelta

from betwatch import Betwatch, OddsFrame, ReadyFrame, StreamFrame


def run(label: str) -> None:
    key = os.environ.get("BETWATCH_API_KEY")
    if not key:
        raise SystemExit("BETWATCH_API_KEY is not set")
    base = os.environ.get("BETWATCH_API_URL", "http://localhost:8888")
    now = datetime.now(UTC)
    with Betwatch(api_key=key, base_url=base) as client:
        page = client.events.list(
            start_from=(now - timedelta(hours=6)).isoformat().replace("+00:00", "Z"),
            start_to=(now + timedelta(hours=18)).isoformat().replace("+00:00", "Z"),
            limit=5,
        )
        print(f"{label} events={len(page)} next={bool(page.next)} cursor={page.cursor!r}")
        if not page.items:
            raise SystemExit(f"{label}: empty /v2/events page")
        event_id = page[0].id
        print(f"{label} first_event={event_id} name={page[0].name!r}")
        card = client.events.snapshot(event_id)
        print(
            f"{label} snapshot event={card.event.id} entrants={len(card.entrants)} "
            f"odds={len(card.odds)} coverage={len(card.coverage)} "
            f"cursor={card.stream.cursor!r}"
        )
        if not card.event.id:
            raise SystemExit(f"{label}: snapshot missing event id")
        frames: list[StreamFrame] = []
        try:
            with client.follow(card, reconnect=False) as stream:
                for frame in stream:
                    frames.append(frame)
                    # snapshot=none emits ready then waits; one typed frame is enough
                    break
        except Exception as exc:
            print(f"{label} stream_error={type(exc).__name__}:{exc}")
            raise SystemExit(f"{label}: stream failed") from exc
        kinds = [frame.type for frame in frames]
        print(f"{label} stream_frames={kinds} last_cursor={frames[-1].cursor if frames else None}")
        if not frames:
            raise SystemExit(f"{label}: stream yielded no frames")
        assert isinstance(frames[0], (ReadyFrame, OddsFrame)) or frames[0].type


if __name__ == "__main__":
    label = sys.argv[1] if len(sys.argv) > 1 else "run"
    run(label)

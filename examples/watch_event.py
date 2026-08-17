"""Snapshot one race and follow live odds. Ctrl+C to stop."""

from betwatch import Betwatch, OddsFrame

try:
    with Betwatch() as client:
        races = client.events.list(sport="thoroughbred", country="au")
        race = races.next_open or (races[0] if races else None)
        if race is None:
            raise SystemExit("No races found in the current event window")
        print(race.name, race.id, race.start_at)
        with client.watch(race.id) as live:
            card = live.snapshot
            assert card is not None
            print(f"runners={len(card.entrants)} odds={len(card.odds)}")
            for frame in live:
                if isinstance(frame, OddsFrame) and frame.data.price is not None:
                    print(frame.data.source.id, frame.data.price)
except KeyboardInterrupt:
    print("Stopped")

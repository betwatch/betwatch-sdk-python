from betwatch import Betwatch

api_key = None
with Betwatch(api_key=api_key) as client:
    races = client.events.list(sport="thoroughbred", country="au", limit=20)
    race = races.next_open or (races[0] if races else None)
    if race is None:
        raise SystemExit("No races found in the current event window")
    card = client.events.snapshot(race.id)
    print(card.event.name, card.event.status)

    for runner in card.entrants:
        if runner.scratched:
            continue
        print(f"{runner.number}. {runner.name}")
        print("  Best:", card.best_price(runner))
        print("  Lowest:", card.lowest_price(runner))
        print("  Sportsbet:", card.price(runner, "sportsbet"))

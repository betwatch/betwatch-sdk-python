import betwatch

# You can set your API here if you like to live dangerously.
# Otherwise set BETWATCH_API_KEY (or `fnox exec --`).
api_key = None

client = betwatch.connect(api_key)

races = client.events.list(sport="thoroughbred", country="au", limit=20)
print(f"Found {len(races)} races")
for race in races:
    print(race.name, race.start_at, race.status)

race = races.next_open or races[0]
card = client.events.snapshot(race.id)
print(f"\n{card.event.name} — {len(card.entrants)} runners")
for runner in card.entrants:
    print(f"{runner.number}. {runner.name}")
    for quote in card.quotes(runner):
        print(f"  {quote.source.name}: {quote.price}")

class RaceProjection:
    def __init__(
        self,
        markets=False,
        place_markets=False,
        flucs=False,
        links=False,
        betfair=False,
    ) -> None:
        self.markets = markets
        self.place_markets = place_markets
        self.links = links
        self.flucs = flucs
        self.betfair = betfair

class RaceProjection:
    def __init__(self, markets=False, flucs=False, links=False) -> None:
        # TODO: add more fields and allow for more flexible filtering
        self.markets = markets
        self.links = links
        self.flucs = flucs

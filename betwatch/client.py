from typing import List, Union
from gql import Client
from gql.transport.aiohttp import AIOHTTPTransport
import typedload
from betwatch.queries import QUERY_GET_RACE, QUERY_GET_RACES
from betwatch.types.race import Race
from betwatch.__about__ import __version__


class BetwatchClient:
    def __init__(self, api_key: str):
        self.api_key = api_key
        self._gql_transport = AIOHTTPTransport(
            url="https://api.betwatch.com/query",
            headers={
                "X-API-KEY": self.api_key,
                "User-Agent": f"betwatch-python-{__version__}",
            },
        )
        # Create a GraphQL client using the defined transport
        self._gql_client = Client(
            transport=self._gql_transport,
            fetch_schema_from_transport=True,
            parse_results=True,
        )

    def get_races(self, date_from: str, date_to: str) -> List[Race]:
        query = QUERY_GET_RACES
        variables = {"dateFrom": date_from, "dateTo": date_to}
        result = self._gql_client.execute(query, variable_values=variables)

        if result.get("races"):
            return typedload.load(result["races"], List[Race])

        return []

    def get_race(self, race_id: str) -> Union[Race, None]:
        return self.get_race_by_id(race_id)

    def get_race_by_id(self, race_id: str) -> Union[Race, None]:
        query = QUERY_GET_RACE
        variables = {"id": race_id}
        result = self._gql_client.execute(query, variable_values=variables)

        if result.get("race"):
            return typedload.load(result["race"], Race)
        return None

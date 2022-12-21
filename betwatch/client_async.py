from typing import List
from gql import Client
from gql.transport.aiohttp import AIOHTTPTransport
import typedload
from betwatch.queries import QUERY_GET_RACE, QUERY_GET_RACES
from betwatch.types.race import Race


class BetwatchAsyncClient:
    def __init__(self, api_key: str):
        self.api_key = api_key
        self._gql_transport = AIOHTTPTransport(
            url="https://api.betwatch.com/query", headers={"X-API-KEY": self.api_key}
        )
        # Create a GraphQL client using the defined transport
        self._gql_client = Client(
            transport=self._gql_transport,
            fetch_schema_from_transport=True,
            parse_results=True,
        )

    async def get_races(self, date_from: str, date_to: str):
        query = QUERY_GET_RACES
        variables = {"dateFrom": date_from, "dateTo": date_to}

        async with self._gql_client as session:
            result = await session.execute(query, variable_values=variables)
            if result.get("races"):
                return typedload.load(result["races"], List[Race])

            return None

    async def get_race(self, race_id: str):
        return await self.get_race_by_id(race_id)

    async def get_race_by_id(self, race_id: str):
        query = QUERY_GET_RACE
        variables = {"id": race_id}

        async with self._gql_client as session:
            result = await session.execute(query, variable_values=variables)

            if result.get("race"):
                return typedload.load(result["race"], Race)
            return None

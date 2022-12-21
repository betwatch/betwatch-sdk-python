from typing import List
from gql import Client, gql
from gql.transport.aiohttp import AIOHTTPTransport
import typedload
from betwatch.types.race import Race


class BetwatchClient:
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

    def get_races(self, date_from: str, date_to: str):
        query = gql(
            """
            query GetRaces($dateFrom: String!, $dateTo: String!) {
                races(dateFrom: $dateFrom, dateTo: $dateTo) {
                    id
                    meeting {
                        id
                        location
                        track
                        type
                        date
                    }
                    name
                    number
                    status
                    startTime
                    results
                }
            }
            """
        )
        variables = {"dateFrom": date_from, "dateTo": date_to}
        result = self._gql_client.execute(query, variable_values=variables)

        if result.get("races"):
            return typedload.load(result["races"], List[Race])

        return None

    def get_race(self, race_id: str):
        return self.get_race_by_id(race_id)

    def get_race_by_id(self, race_id: str):
        query = gql(
            """
            query GetRace($id: ID!) {
                race(id: $id) {
                    id
                    meeting {
                        id
                        location
                        track
                        type
                        date
                    }
                    name
                    number
                    status
                    distance
                    startTime
                    results
                    links {
                        bookmaker
                        lastSuccessfulPriceUpdate
                    }
                    runners {
                        id
                        number
                        name
                        scratchedTime

                        bookmakerMarkets {
                            id
                            bookmaker
                            fixedWin {
                                price
                                lastUpdated
                                flucs {
                                    price
                                    lastUpdated
                                }
                            }
                            fixedPlace {
                                price
                                lastUpdated
                                flucs {
                                    price
                                    lastUpdated
                                }
                            }
                        }
                    }
                }
            }
            """
        )
        variables = {"id": race_id}
        result = self._gql_client.execute(query, variable_values=variables)

        if result.get("race"):
            return typedload.load(result["race"], Race)
        return None

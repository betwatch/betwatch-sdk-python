from gql import gql
from graphql import DocumentNode

from betwatch.types import RaceProjection


def get_race_query(projection: RaceProjection) -> str:
    """Get a GQL query based on a projection."""

    bookmakers = (
        "["
        + ",".join(['"' + str(bookmaker) + '"' for bookmaker in projection.bookmakers])
        + "]"
    )

    if projection.flucs and projection.bookmakers:
        bookmakers_with_flucs = bookmakers
        bookmakers = '[""]'
    else:
        bookmakers_with_flucs = "[]"

    runners_gql = (
        "runners { id betfairId name number scratchedTime barrier trainerName riderName "
        + (
            "betfairMarkets { id sp marketName marketId totalMatched marketTotalMatched lastPriceTraded back { price size lastUpdated } lay { price size lastUpdated } } "
            if projection.betfair
            else ""
        )
        + (
            (
                "bookmakerMarkets(bookmakers: "
                + bookmakers
                + ", bookmakersWithFlucs: "
                + bookmakers_with_flucs
                + ") { id bookmaker "
                + "fixedWin { price lastUpdated "
                + ("flucs { price lastUpdated } " if projection.flucs else "")
                + "} "
                + (
                    "fixedPlace { price lastUpdated "
                    + ("flucs { price lastUpdated } " if projection.flucs else "")
                    + "} "
                    if projection.place_markets
                    else ""
                )
                + "} "
            )
            if projection.markets
            else ""
        )
        + "}"
    )

    return (
        " id betfairMapping { win place } meeting { id location track type date } "
        + "classConditions name number status startTime results distance "
        + runners_gql
        + (
            " links { bookmaker lastSuccessfulPriceUpdate navLink fixedWin } "
            if projection.links
            else ""
        )
    )


SUBSCRIPTION_RACES_UPDATES = gql(
    """
    subscription RacesUpdates($dateFrom: String!, $dateTo: String!) {
      racesUpdates(dateFrom: $dateFrom, dateTo: $dateTo) {
        id
        status
        startTime
      }
    }
    """
)

SUBSCRIPTION_RUNNER_UPDATES = gql(
    """
    subscription RunnerUpdates($id: ID!) {
      runnerUpdates(id: $id) {
        id
        scratchedTime
      }
    }
    """
)


def subscription_race_price_updates(projection: RaceProjection) -> DocumentNode:
    return gql(
        """
    subscription PriceUpdates($id: ID!) {
      priceUpdates(id: $id) {
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
        """
        + (
            """fixedPlace {
          price
          lastUpdated
          flucs {
            price
            lastUpdated
          }
        }
        """
            if projection.place_markets
            else ""
        )
        + """}
    }
    """
    )


SUBSCRIPTION_BETFAIR_UPDATES = gql(
    """
    subscription BetfairUpdates($id: ID!) {
      betfairUpdates(id: $id) {
        id
        sp
        totalMatched
        marketTotalMatched
        back {
          price
          size
          lastUpdated
        }
        lay {
          price
          size
          lastUpdated
        }
      }
    }
    """
)


def query_get_races(projection: RaceProjection) -> DocumentNode:
    return gql(
        """
            query GetRaces($limit: Int, $offset: Int, $types: [RaceType!], $tracks: [String!], $locations: [String!], $hasBookmakers: [String!], $hasRunners: [String!], $hasTrainers: [String!], $hasRiders: [String!], $dateFrom: String!, $dateTo: String!) {
                races(limit: $limit, offset: $offset, types: $types, tracks: $tracks, locations: $locations, hasBookmakers: $hasBookmakers, hasRunners: $hasRunners, hasTrainers: $hasTrainers, hasRiders: $hasRiders, dateFrom: $dateFrom, dateTo: $dateTo) {
        """
        + get_race_query(projection)
        + """
                }
            }
        """
    )


def query_get_race(projection: RaceProjection) -> DocumentNode:
    return gql(
        """
    query GetRace($id: ID!) {
        race(id: $id) {
         """
        + get_race_query(projection)
        + """
        }
    }
    """
    )


QUERY_GET_LAST_SUCCESSFUL_PRICE_UPDATE = gql(
    """
    query GetRace($id: ID!) {
        race(id: $id) {
            id
            status
            links {
                bookmaker
                lastSuccessfulPriceUpdate
            }
        }
    }
    """
)

MUTATION_UPDATE_USER_EVENT_DATA = gql(
    """
    mutation UpdateUserEventData($input: UpdateUserEventDataInput!) {
        updateUserEventData(input: $input) {
            eventId
            data {
                columnName
                selectionData {
                    selectionId
                    value
                }
            }
        }
    }
    """
)

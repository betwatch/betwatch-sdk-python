from gql import gql
from betwatch.types import RaceProjection
from graphql import DocumentNode


def get_race_query_from_projection(projection: RaceProjection) -> str:
    """Get a GQL query based on a projection."""

    runners_gql = (
        "runners { id name number "
        + (
            "bookmakerMarkets { id bookmaker "
            + "fixedWin { price lastUpdated "
            + ("flucs { price lastUpdated } " if projection.flucs else "")
            + "} "
            + "fixedPlace { price lastUpdated "
            + ("flucs { price lastUpdated } " if projection.flucs else "")
            + "} } "
        )
        + "}"
        if projection.markets
        else ""
    )

    return (
        " id meeting { id location track type date } "
        + "classConditions name number status startTime results "
        + runners_gql
        + (
            " links { bookmaker lastSuccessfulPriceUpdate navLink } "
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

SUBSCRIPTION_PRICE_UPDATES = gql(
    """
    subscription PriceUpdates($id: ID!) {
      priceUpdates(id: $id) {
        id
        bookmaker
        fixedPlace {
          price
          lastUpdated
          flucs {
            price
            lastUpdated
          }
        }
        fixedWin {
          price
          lastUpdated
          flucs {
            price
            lastUpdated
          }
        }
      }
    }
    """
)


def query_get_races(projection: RaceProjection) -> DocumentNode:
    return gql(
        """
            query GetRaces($dateFrom: String!, $dateTo: String!) {
                races(dateFrom: $dateFrom, dateTo: $dateTo) {
        """
        + get_race_query_from_projection(projection)
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
        + get_race_query_from_projection(projection)
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

from gql import gql

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

QUERY_GET_RACES = gql(
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
            classConditions
            name
            number
            status
            startTime
            results
            runners {
                id
                name
                number
            }
        }
    }
    """
)

QUERY_GET_RACES_WITH_MARKETS = gql(
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
            classConditions
            name
            number
            status
            startTime
            results
            runners {
                id
                name
                number
                bookmakerMarkets {
                    id
                    bookmaker
                    fixedWin {
                        price
                        lastUpdated
                    }
                    fixedPlace {
                        price
                        lastUpdated
                    }
                }
            }
        }
    }
    """
)


QUERY_GET_RACE = gql(
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
            classConditions
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

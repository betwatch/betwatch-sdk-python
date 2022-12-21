from gql import gql

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
                    name
                    number
                    status
                    startTime
                    results
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

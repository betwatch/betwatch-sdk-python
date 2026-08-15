from __future__ import annotations

import betwatch
from betwatch import Betwatch, FilterRequiredError, NotFoundError, __version__


def test_version_is_prerelease() -> None:
    assert __version__ == "2.0.0b1"


def test_no_graphql_get_races_surface() -> None:
    assert not hasattr(betwatch, "get_races")
    assert not hasattr(Betwatch, "get_races")
    assert not hasattr(Betwatch, "get_race")
    assert callable(betwatch.connect)
    assert callable(betwatch.connect_async)


def test_odds_list_requires_narrowing_filter() -> None:
    client = Betwatch(api_key="bw_test", base_url="http://localhost:8888")
    try:
        with __import__("pytest").raises(FilterRequiredError):
            client.odds.list()
        with __import__("pytest").raises(FilterRequiredError):
            client.entrants.list()
    finally:
        client.close()


def test_typed_exceptions_are_public() -> None:
    assert issubclass(NotFoundError, betwatch.APIStatusError)

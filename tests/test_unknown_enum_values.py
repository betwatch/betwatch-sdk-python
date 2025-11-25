"""Test that unknown enum values are handled gracefully"""

import pytest
from betwatch.types import Bookmaker
from betwatch.types.race import (
    RaceLink,
    Meeting,
    Race,
    RaceUpdate,
    MeetingType,
    RaceStatus,
)
from betwatch.types.markets import BookmakerMarket


def test_race_link_unknown_bookmaker():
    """Test that RaceLink handles unknown bookmakers gracefully"""
    # Create a RaceLink with an unknown bookmaker
    race_link = RaceLink(
        _bookmaker="UnknownBookmaker",
        nav_link="http://example.com",
    )

    # Should return the string instead of raising an exception
    assert race_link.bookmaker == "UnknownBookmaker"
    assert isinstance(race_link.bookmaker, str)


def test_race_link_known_bookmaker():
    """Test that RaceLink handles known bookmakers correctly"""
    # Create a RaceLink with a known bookmaker
    race_link = RaceLink(
        _bookmaker="Tab",
        nav_link="http://example.com",
    )

    # Should return the Bookmaker enum
    assert race_link.bookmaker == Bookmaker.TAB
    assert isinstance(race_link.bookmaker, Bookmaker)


def test_bookmaker_market_unknown_bookmaker():
    """Test that BookmakerMarket handles unknown bookmakers gracefully"""
    # Create a BookmakerMarket with an unknown bookmaker
    market = BookmakerMarket(
        id="test123",
        _bookmaker="NewBookmaker2024",
    )

    # Should return the string instead of raising an exception
    assert market.bookmaker == "NewBookmaker2024"
    assert isinstance(market.bookmaker, str)


def test_bookmaker_market_known_bookmaker():
    """Test that BookmakerMarket handles known bookmakers correctly"""
    # Create a BookmakerMarket with a known bookmaker
    market = BookmakerMarket(
        id="test123",
        _bookmaker="Sportsbet",
    )

    # Should return the Bookmaker enum
    assert market.bookmaker == Bookmaker.SPORTSBET
    assert isinstance(market.bookmaker, Bookmaker)


def test_case_insensitive_bookmaker():
    """Test that bookmaker matching is case insensitive"""
    # Create a RaceLink with different case
    race_link = RaceLink(
        _bookmaker="sportsbet",  # lowercase
        nav_link="http://example.com",
    )

    # Should match case-insensitively and return the enum
    assert race_link.bookmaker == Bookmaker.SPORTSBET
    assert isinstance(race_link.bookmaker, Bookmaker)


def test_meeting_unknown_type():
    """Test that Meeting handles unknown meeting types gracefully"""
    # Create a Meeting with an unknown type
    meeting = Meeting(
        id="test123",
        _type="Virtual",  # Unknown meeting type
        date="2024-01-01",
        track="Test Track",
        location="Test Location",
    )

    # Should return the string instead of raising an exception
    assert meeting.type == "Virtual"
    assert isinstance(meeting.type, str)


def test_meeting_known_type():
    """Test that Meeting handles known meeting types correctly"""
    # Create a Meeting with a known type
    meeting = Meeting(
        id="test123",
        _type="Thoroughbred",
        date="2024-01-01",
        track="Test Track",
        location="Test Location",
    )

    # Should return the MeetingType enum
    assert meeting.type == MeetingType.THOROUGHBRED
    assert isinstance(meeting.type, MeetingType)


def test_race_unknown_status():
    """Test that Race handles unknown race statuses gracefully"""
    # Create a Race with an unknown status
    race = Race(
        id="test123",
        _status="Postponed",  # Unknown status
    )

    # Should return the string instead of raising an exception
    assert race.status == "Postponed"
    assert isinstance(race.status, str)


def test_race_known_status():
    """Test that Race handles known race statuses correctly"""
    # Create a Race with a known status
    race = Race(
        id="test123",
        _status="Open",
    )

    # Should return the RaceStatus enum
    assert race.status == RaceStatus.OPEN
    assert isinstance(race.status, RaceStatus)


def test_race_none_status():
    """Test that Race handles None status correctly"""
    # Create a Race with None status
    race = Race(
        id="test123",
        _status=None,
    )

    # Should return None
    assert race.status is None


def test_race_update_unknown_status():
    """Test that RaceUpdate handles unknown race statuses gracefully"""
    # Create a RaceUpdate with an unknown status
    race_update = RaceUpdate(
        id="test123",
        _status="Delayed",  # Unknown status
        _start_time="2024-01-01T10:00:00Z",
    )

    # Should return the string instead of raising an exception
    assert race_update.status == "Delayed"
    assert isinstance(race_update.status, str)


def test_race_update_known_status():
    """Test that RaceUpdate handles known race statuses correctly"""
    # Create a RaceUpdate with a known status
    race_update = RaceUpdate(
        id="test123",
        _status="Resulted",
        _start_time="2024-01-01T10:00:00Z",
    )

    # Should return the RaceStatus enum
    assert race_update.status == RaceStatus.RESULTED
    assert isinstance(race_update.status, RaceStatus)


def test_case_insensitive_meeting_type():
    """Test that meeting type matching is case insensitive"""
    # Create a Meeting with different case
    meeting = Meeting(
        id="test123",
        _type="greyhound",  # lowercase
        date="2024-01-01",
        track="Test Track",
        location="Test Location",
    )

    # Should match case-insensitively and return the enum
    assert meeting.type == MeetingType.GREYHOUND
    assert isinstance(meeting.type, MeetingType)

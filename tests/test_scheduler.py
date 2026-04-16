"""Tests for follow-up date scheduling logic."""
import pytest
from datetime import datetime, timedelta
from bot.scheduler import compute_followup_date


class TestComputeFollowupDate:
    def test_monday_returns_7_days_later(self):
        # Monday = weekday 0
        monday = datetime(2024, 4, 1)  # April 1, 2024 is a Monday
        assert monday.weekday() == 0
        result = compute_followup_date(monday)
        assert result == monday + timedelta(days=7)
        assert result.weekday() == 0  # still a Monday

    def test_tuesday_returns_7_days_later(self):
        tuesday = datetime(2024, 4, 2)
        assert tuesday.weekday() == 1
        result = compute_followup_date(tuesday)
        assert result == tuesday + timedelta(days=7)

    def test_wednesday_returns_7_days_later(self):
        wednesday = datetime(2024, 4, 3)
        assert wednesday.weekday() == 2
        result = compute_followup_date(wednesday)
        assert result == wednesday + timedelta(days=7)

    def test_thursday_returns_7_days_later(self):
        thursday = datetime(2024, 4, 4)
        assert thursday.weekday() == 3
        result = compute_followup_date(thursday)
        assert result == thursday + timedelta(days=7)

    def test_friday_returns_following_monday(self):
        friday = datetime(2024, 4, 5)
        assert friday.weekday() == 4
        result = compute_followup_date(friday)
        assert result == friday + timedelta(days=3)
        assert result.weekday() == 0  # Monday

    def test_saturday_returns_following_monday(self):
        saturday = datetime(2024, 4, 6)
        assert saturday.weekday() == 5
        result = compute_followup_date(saturday)
        assert result == saturday + timedelta(days=2)
        assert result.weekday() == 0  # Monday

    def test_sunday_returns_next_day_monday(self):
        sunday = datetime(2024, 4, 7)
        assert sunday.weekday() == 6
        result = compute_followup_date(sunday)
        assert result == sunday + timedelta(days=1)
        assert result.weekday() == 0  # Monday

    def test_preserves_time_component(self):
        """Follow-up should keep the same time-of-day as the initial send."""
        sent = datetime(2024, 4, 1, 14, 30, 0)  # Monday 2:30 PM
        result = compute_followup_date(sent)
        assert result.hour == 14
        assert result.minute == 30

    def test_friday_followup_is_sooner_than_7_days(self):
        """A Friday send should follow up in 3 days (not 7), landing on Monday."""
        friday = datetime(2024, 4, 5)
        result = compute_followup_date(friday)
        assert result < friday + timedelta(days=7)
        assert result.weekday() == 0  # lands on a Monday

    @pytest.mark.parametrize("weekday,expected_delta", [
        (0, 7),  # Mon
        (1, 7),  # Tue
        (2, 7),  # Wed
        (3, 7),  # Thu
        (4, 3),  # Fri → Mon
        (5, 2),  # Sat → Mon
        (6, 1),  # Sun → Mon
    ])
    def test_all_weekdays(self, weekday, expected_delta):
        # Build a datetime that falls on the target weekday
        base = datetime(2024, 4, 1)  # Monday
        sent = base + timedelta(days=weekday)
        assert sent.weekday() == weekday
        result = compute_followup_date(sent)
        assert result == sent + timedelta(days=expected_delta)

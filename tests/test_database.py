"""Tests for SQLite database operations."""
import os
import pytest
import tempfile
from datetime import datetime, timedelta, timezone
from unittest.mock import patch


# Patch DB_PATH before importing database module
@pytest.fixture(autouse=True)
def isolated_db(tmp_path, monkeypatch):
    """Each test gets its own fresh SQLite DB in a temp dir."""
    db_file = str(tmp_path / "test_connections.db")
    monkeypatch.setattr("bot.database.DB_PATH", db_file)
    from bot.database import init_db
    init_db()
    yield db_file


from bot.database import (
    upsert_connection,
    mark_umn_student,
    mark_initial_sent,
    mark_followup_sent,
    get_pending_initial,
    get_pending_followup,
    get_stats,
)

PROFILE_URL = "https://www.linkedin.com/in/test-user"
PROFILE_URL_2 = "https://www.linkedin.com/in/test-user-2"


class TestUpsertConnection:
    def test_inserts_new_connection(self):
        result = upsert_connection(PROFILE_URL, "Alice", "Alice Smith")
        assert result is True

    def test_duplicate_returns_false(self):
        upsert_connection(PROFILE_URL, "Alice", "Alice Smith")
        result = upsert_connection(PROFILE_URL, "Alice", "Alice Smith")
        assert result is False

    def test_different_urls_both_inserted(self):
        r1 = upsert_connection(PROFILE_URL, "Alice", "Alice Smith")
        r2 = upsert_connection(PROFILE_URL_2, "Bob", "Bob Jones")
        assert r1 is True
        assert r2 is True


class TestMarkUmnStudent:
    def test_sets_status_to_skipped_umn(self):
        upsert_connection(PROFILE_URL, "Alice", "Alice Smith")
        mark_umn_student(PROFILE_URL)
        stats = get_stats()
        assert stats.get("skipped_umn", 0) == 1

    def test_sets_is_umn_student_flag(self, isolated_db):
        import sqlite3
        upsert_connection(PROFILE_URL, "Alice", "Alice Smith")
        mark_umn_student(PROFILE_URL)
        conn = sqlite3.connect(isolated_db)
        row = conn.execute(
            "SELECT is_umn_student FROM connections WHERE linkedin_profile_url=?",
            (PROFILE_URL,)
        ).fetchone()
        conn.close()
        assert row[0] == 1


class TestMarkInitialSent:
    def test_updates_status_to_initial_sent(self):
        upsert_connection(PROFILE_URL, "Alice", "Alice Smith")
        followup_due = datetime.now(timezone.utc) + timedelta(days=7)
        mark_initial_sent(PROFILE_URL, followup_due)
        stats = get_stats()
        assert stats.get("initial_sent", 0) == 1

    def test_stores_followup_due_at(self, isolated_db):
        import sqlite3
        upsert_connection(PROFILE_URL, "Alice", "Alice Smith")
        followup_due = datetime(2024, 4, 15, 10, 0, 0)
        mark_initial_sent(PROFILE_URL, followup_due)
        conn = sqlite3.connect(isolated_db)
        row = conn.execute(
            "SELECT followup_due_at FROM connections WHERE linkedin_profile_url=?",
            (PROFILE_URL,)
        ).fetchone()
        conn.close()
        assert row[0] is not None

    def test_stores_initial_message_sent_at(self, isolated_db):
        import sqlite3
        upsert_connection(PROFILE_URL, "Alice", "Alice Smith")
        followup_due = datetime.now(timezone.utc) + timedelta(days=7)
        mark_initial_sent(PROFILE_URL, followup_due)
        conn = sqlite3.connect(isolated_db)
        row = conn.execute(
            "SELECT initial_message_sent_at FROM connections WHERE linkedin_profile_url=?",
            (PROFILE_URL,)
        ).fetchone()
        conn.close()
        assert row[0] is not None


class TestMarkFollowupSent:
    def test_updates_status_to_followup_sent(self):
        upsert_connection(PROFILE_URL, "Alice", "Alice Smith")
        followup_due = datetime.now(timezone.utc) - timedelta(days=1)
        mark_initial_sent(PROFILE_URL, followup_due)
        mark_followup_sent(PROFILE_URL)
        stats = get_stats()
        assert stats.get("followup_sent", 0) == 1

    def test_stores_followup_sent_at(self, isolated_db):
        import sqlite3
        upsert_connection(PROFILE_URL, "Alice", "Alice Smith")
        followup_due = datetime.now(timezone.utc) - timedelta(days=1)
        mark_initial_sent(PROFILE_URL, followup_due)
        mark_followup_sent(PROFILE_URL)
        conn = sqlite3.connect(isolated_db)
        row = conn.execute(
            "SELECT followup_sent_at FROM connections WHERE linkedin_profile_url=?",
            (PROFILE_URL,)
        ).fetchone()
        conn.close()
        assert row[0] is not None


class TestGetPendingInitial:
    def test_returns_pending_within_window(self):
        upsert_connection(PROFILE_URL, "Alice", "Alice Smith")
        results = get_pending_initial(window_hours=2, limit=10)
        assert any(r["linkedin_profile_url"] == PROFILE_URL for r in results)

    def test_excludes_already_messaged(self):
        upsert_connection(PROFILE_URL, "Alice", "Alice Smith")
        mark_initial_sent(PROFILE_URL, datetime.now(timezone.utc) + timedelta(days=7))
        results = get_pending_initial(window_hours=2, limit=10)
        assert not any(r["linkedin_profile_url"] == PROFILE_URL for r in results)

    def test_excludes_umn_students(self):
        upsert_connection(PROFILE_URL, "Alice", "Alice Smith")
        mark_umn_student(PROFILE_URL)
        results = get_pending_initial(window_hours=2, limit=10)
        assert not any(r["linkedin_profile_url"] == PROFILE_URL for r in results)

    def test_respects_limit(self):
        for i in range(10):
            upsert_connection(f"{PROFILE_URL}-{i}", "User", f"User {i}")
        results = get_pending_initial(window_hours=2, limit=3)
        assert len(results) <= 3

    def test_retries_old_pending_connections(self, isolated_db):
        """Pending connections older than window_hours should still be retried."""
        import sqlite3
        old_time = (datetime.now(timezone.utc) - timedelta(hours=3)).strftime("%Y-%m-%d %H:%M:%S")
        conn = sqlite3.connect(isolated_db)
        conn.execute(
            "INSERT INTO connections (linkedin_profile_url, first_name, detected_at) VALUES (?,?,?)",
            (PROFILE_URL, "Alice", old_time)
        )
        conn.commit()
        conn.close()
        results = get_pending_initial(window_hours=2, limit=10)
        # Old pending connections should still be returned for retry
        assert any(r["linkedin_profile_url"] == PROFILE_URL for r in results)


class TestGetPendingFollowup:
    def test_returns_due_followups(self):
        upsert_connection(PROFILE_URL, "Alice", "Alice Smith")
        past_due = datetime.now(timezone.utc) - timedelta(hours=1)
        mark_initial_sent(PROFILE_URL, past_due)
        results = get_pending_followup(limit=10)
        assert any(r["linkedin_profile_url"] == PROFILE_URL for r in results)

    def test_excludes_future_followups(self):
        upsert_connection(PROFILE_URL, "Alice", "Alice Smith")
        future = datetime.now(timezone.utc) + timedelta(days=5)
        mark_initial_sent(PROFILE_URL, future)
        results = get_pending_followup(limit=10)
        assert not any(r["linkedin_profile_url"] == PROFILE_URL for r in results)

    def test_excludes_already_sent_followups(self):
        upsert_connection(PROFILE_URL, "Alice", "Alice Smith")
        past_due = datetime.now(timezone.utc) - timedelta(hours=1)
        mark_initial_sent(PROFILE_URL, past_due)
        mark_followup_sent(PROFILE_URL)
        results = get_pending_followup(limit=10)
        assert not any(r["linkedin_profile_url"] == PROFILE_URL for r in results)

    def test_respects_limit(self):
        for i in range(10):
            url = f"{PROFILE_URL}-{i}"
            upsert_connection(url, "User", f"User {i}")
            past_due = datetime.now(timezone.utc) - timedelta(hours=1)
            mark_initial_sent(url, past_due)
        results = get_pending_followup(limit=3)
        assert len(results) <= 3


class TestGetStats:
    def test_empty_db_returns_empty_dict(self):
        stats = get_stats()
        assert stats == {}

    def test_counts_by_status(self):
        upsert_connection(PROFILE_URL, "Alice", "Alice Smith")
        upsert_connection(PROFILE_URL_2, "Bob", "Bob Jones")
        mark_umn_student(PROFILE_URL_2)
        stats = get_stats()
        assert stats.get("pending", 0) == 1
        assert stats.get("skipped_umn", 0) == 1

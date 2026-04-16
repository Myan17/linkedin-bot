"""Tests for message template generation."""
import os
import pytest
from unittest.mock import patch
from bot.templates import initial_message, followup_message


FAKE_RESUME = "https://drive.google.com/test-resume"


class TestInitialMessage:
    def test_contains_first_name(self):
        with patch.dict(os.environ, {"RESUME_LINK": FAKE_RESUME}):
            msg = initial_message("Alice")
        assert "Alice" in msg

    def test_contains_resume_link(self):
        with patch.dict(os.environ, {"RESUME_LINK": FAKE_RESUME}):
            msg = initial_message("Alice")
        assert FAKE_RESUME in msg

    def test_mentions_school_from_env(self):
        with patch.dict(os.environ, {"RESUME_LINK": FAKE_RESUME, "SCHOOL": "MIT"}):
            msg = initial_message("Bob")
        assert "MIT" in msg

    def test_greets_with_name(self):
        with patch.dict(os.environ, {"RESUME_LINK": FAKE_RESUME}):
            msg = initial_message("Carlos")
        assert msg.startswith("Hey Carlos")

    def test_missing_env_var_uses_placeholder(self):
        env = {k: v for k, v in os.environ.items() if k != "RESUME_LINK"}
        with patch.dict(os.environ, env, clear=True):
            msg = initial_message("Dave")
        assert "[RESUME_LINK]" in msg

    def test_different_names_produce_different_messages(self):
        with patch.dict(os.environ, {"RESUME_LINK": FAKE_RESUME}):
            msg1 = initial_message("Alice")
            msg2 = initial_message("Bob")
        assert msg1 != msg2

    def test_is_string(self):
        with patch.dict(os.environ, {"RESUME_LINK": FAKE_RESUME}):
            msg = initial_message("Eve")
        assert isinstance(msg, str)

    def test_non_empty(self):
        with patch.dict(os.environ, {"RESUME_LINK": FAKE_RESUME}):
            msg = initial_message("Frank")
        assert len(msg) > 50

    def test_mentions_internship_and_fulltime(self):
        with patch.dict(os.environ, {"RESUME_LINK": FAKE_RESUME}):
            msg = initial_message("Grace")
        assert "internship" in msg.lower() or "full-time" in msg.lower()


class TestFollowupMessage:
    def test_contains_first_name(self):
        with patch.dict(os.environ, {"RESUME_LINK": FAKE_RESUME}):
            msg = followup_message("Alice")
        assert "Alice" in msg

    def test_contains_resume_link(self):
        with patch.dict(os.environ, {"RESUME_LINK": FAKE_RESUME}):
            msg = followup_message("Alice")
        assert FAKE_RESUME in msg

    def test_greets_with_name(self):
        with patch.dict(os.environ, {"RESUME_LINK": FAKE_RESUME}):
            msg = followup_message("Bob")
        assert msg.startswith("Hi Bob")

    def test_different_from_initial(self):
        with patch.dict(os.environ, {"RESUME_LINK": FAKE_RESUME}):
            initial = initial_message("Carol")
            followup = followup_message("Carol")
        assert initial != followup

    def test_missing_env_var_uses_placeholder(self):
        env = {k: v for k, v in os.environ.items() if k != "RESUME_LINK"}
        with patch.dict(os.environ, env, clear=True):
            msg = followup_message("Dave")
        assert "[RESUME_LINK]" in msg

    def test_is_string(self):
        with patch.dict(os.environ, {"RESUME_LINK": FAKE_RESUME}):
            msg = followup_message("Eve")
        assert isinstance(msg, str)

    def test_non_empty(self):
        with patch.dict(os.environ, {"RESUME_LINK": FAKE_RESUME}):
            msg = followup_message("Frank")
        assert len(msg) > 30

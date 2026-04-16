"""
Tests for LinkedIn DOM interaction helpers.
Uses mocked Playwright Page objects — no real browser required.
"""
import pytest
from unittest.mock import MagicMock, patch, call, ANY
from bot.linkedin import (
    _try_click,
    _safe_text,
    _close_open_chats,
    is_umn_student,
    send_message,
    UMN_KEYWORDS,
)


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def make_page(inner_text="", goto_url=None):
    page = MagicMock()
    page.url = goto_url or "https://www.linkedin.com/in/test"
    page.inner_text.return_value = inner_text
    return page


def _make_visible_compose_loc():
    """Return a locator mock that looks like a visible compose box."""
    loc = MagicMock()
    loc.first.wait_for.return_value = None
    loc.first.is_visible.return_value = True
    loc.first.evaluate.return_value = True   # JS send returns True
    loc.first.click.return_value = None
    return loc


# ---------------------------------------------------------------------------
# _try_click
# ---------------------------------------------------------------------------

class TestTryClick:
    def test_returns_true_on_first_success(self):
        page = MagicMock()
        locator = MagicMock()
        locator.first.click.return_value = None
        page.locator.return_value = locator

        with patch("bot.linkedin.time.sleep"):
            result = _try_click(page, ["button.good"])
        assert result is True

    def test_falls_back_to_second_selector(self):
        page = MagicMock()
        bad_loc = MagicMock()
        bad_loc.first.click.side_effect = Exception("not found")
        good_loc = MagicMock()
        good_loc.first.click.return_value = None

        page.locator.side_effect = [bad_loc, good_loc]
        with patch("bot.linkedin.time.sleep"):
            result = _try_click(page, ["button.bad", "button.good"])
        assert result is True

    def test_returns_false_when_all_selectors_fail(self):
        page = MagicMock()
        bad_loc = MagicMock()
        bad_loc.first.click.side_effect = Exception("not found")
        page.locator.return_value = bad_loc

        with patch("bot.linkedin.time.sleep"):
            result = _try_click(page, ["button.a", "button.b", "button.c"])
        assert result is False

    def test_empty_selector_list_returns_false(self):
        page = MagicMock()
        result = _try_click(page, [])
        assert result is False

    def test_wait_for_failure_tries_next_selector(self):
        """If wait_for raises (element not in DOM), we skip to the next selector."""
        page = MagicMock()
        bad_loc = MagicMock()
        bad_loc.first.wait_for.side_effect = Exception("timeout")
        good_loc = MagicMock()
        good_loc.first.click.return_value = None

        page.locator.side_effect = [bad_loc, good_loc]
        with patch("bot.linkedin.time.sleep"):
            result = _try_click(page, ["button.bad", "button.good"])
        assert result is True

    def test_uses_js_scroll_into_view(self):
        """Verify JS scrollIntoView is called (not Playwright's scroll_into_view_if_needed)."""
        page = MagicMock()
        locator = MagicMock()
        page.locator.return_value = locator

        with patch("bot.linkedin.time.sleep"):
            _try_click(page, ["button.x"])

        locator.first.evaluate.assert_called_once_with(
            "e => e.scrollIntoView({block: 'center', behavior: 'instant'})"
        )


# ---------------------------------------------------------------------------
# _close_open_chats
# ---------------------------------------------------------------------------

class TestCloseOpenChats:
    def test_calls_page_evaluate(self):
        page = MagicMock()
        with patch("bot.linkedin.time.sleep"):
            _close_open_chats(page)
        page.evaluate.assert_called_once()
        # The JS passed must target chat overlay close buttons
        js = page.evaluate.call_args[0][0]
        assert "msg-overlay" in js
        assert "Close" in js

    def test_evaluate_exception_is_swallowed(self):
        """A broken page should not crash the whole send flow."""
        page = MagicMock()
        page.evaluate.side_effect = Exception("page crashed")
        with patch("bot.linkedin.time.sleep"):
            _close_open_chats(page)  # must not raise

    def test_sleeps_after_closing(self):
        """Give the DOM time to settle after clicking close buttons."""
        page = MagicMock()
        with patch("bot.linkedin.time.sleep") as mock_sleep:
            _close_open_chats(page)
        mock_sleep.assert_called_once_with(0.5)


# ---------------------------------------------------------------------------
# _safe_text
# ---------------------------------------------------------------------------

class TestSafeText:
    def test_returns_text_from_first_working_selector(self):
        page = MagicMock()
        loc = MagicMock()
        loc.first.inner_text.return_value = "  some text  "
        loc.first.wait_for.return_value = None
        page.locator.return_value = loc

        result = _safe_text(page, ["section#edu"])
        assert result == "some text"

    def test_falls_back_on_exception(self):
        page = MagicMock()
        bad_loc = MagicMock()
        bad_loc.first.wait_for.side_effect = Exception("timeout")
        good_loc = MagicMock()
        good_loc.first.inner_text.return_value = "found"
        good_loc.first.wait_for.return_value = None

        page.locator.side_effect = [bad_loc, good_loc]
        result = _safe_text(page, ["bad", "good"])
        assert result == "found"

    def test_returns_default_when_all_fail(self):
        page = MagicMock()
        bad_loc = MagicMock()
        bad_loc.first.wait_for.side_effect = Exception("timeout")
        page.locator.return_value = bad_loc

        result = _safe_text(page, ["bad1", "bad2"], default="fallback")
        assert result == "fallback"


# ---------------------------------------------------------------------------
# is_umn_student
# ---------------------------------------------------------------------------

class TestIsUmnStudent:
    def _setup_page(self, edu_text=""):
        page = MagicMock()
        page.goto.return_value = None

        edu_loc = MagicMock()
        edu_loc.first.inner_text.return_value = edu_text
        edu_loc.first.wait_for.return_value = None
        page.locator.return_value = edu_loc

        return page

    @pytest.mark.parametrize("keyword", [
        "University of Minnesota",
        "university of minnesota",
        "UMN",
        "U of M",
        "U of MN",
    ])
    def test_detects_umn_keywords(self, keyword):
        with patch("bot.linkedin._random_delay"), \
             patch("bot.linkedin._try_click"):
            page = self._setup_page(edu_text=keyword)
            result = is_umn_student(page, "https://linkedin.com/in/test")
        assert result is True

    def test_non_umn_student_returns_false(self):
        with patch("bot.linkedin._random_delay"), \
             patch("bot.linkedin._try_click"):
            page = self._setup_page(edu_text="MIT - Computer Science")
            result = is_umn_student(page, "https://linkedin.com/in/test")
        assert result is False

    def test_empty_education_returns_false(self):
        with patch("bot.linkedin._random_delay"), \
             patch("bot.linkedin._try_click"):
            page = self._setup_page(edu_text="")
            page.inner_text.return_value = ""
            result = is_umn_student(page, "https://linkedin.com/in/test")
        assert result is False

    def test_goto_exception_returns_false(self):
        page = MagicMock()
        page.goto.side_effect = Exception("network error")
        result = is_umn_student(page, "https://linkedin.com/in/test")
        assert result is False

    def test_umn_in_headline_detected_via_body_fallback(self):
        """If edu section fails, full body text fallback should still catch UMN."""
        with patch("bot.linkedin._random_delay"), \
             patch("bot.linkedin._try_click"):
            page = MagicMock()
            page.goto.return_value = None
            bad_loc = MagicMock()
            bad_loc.first.wait_for.side_effect = Exception("no edu section")
            page.locator.return_value = bad_loc
            page.inner_text.return_value = "Student at University of Minnesota"

            result = is_umn_student(page, "https://linkedin.com/in/test")
        assert result is True


# ---------------------------------------------------------------------------
# send_message
# ---------------------------------------------------------------------------

class TestSendMessage:
    """
    All tests patch _random_delay, _close_open_chats, and time.sleep to keep
    tests fast, and patch _try_click where the button-click logic is not under
    test.  Compose-box visibility and evaluate() return values are controlled
    per test.
    """

    def _base_patches(self):
        return (
            patch("bot.linkedin._random_delay"),
            patch("bot.linkedin._close_open_chats"),
            patch("bot.linkedin.time.sleep"),
        )

    # ------------------------------------------------------------------
    # Happy path
    # ------------------------------------------------------------------

    def test_returns_true_on_success(self):
        with patch("bot.linkedin._random_delay"), \
             patch("bot.linkedin._close_open_chats"), \
             patch("bot.linkedin.time.sleep"), \
             patch("bot.linkedin._try_click", return_value=True):
            page = MagicMock()
            page.goto.return_value = None
            compose_loc = _make_visible_compose_loc()
            page.locator.return_value = compose_loc

            result = send_message(page, "https://linkedin.com/in/test", "Hello!")
        assert result is True

    def test_message_typed_via_page_keyboard(self):
        """page.keyboard.type() must be called with the full message text."""
        with patch("bot.linkedin._random_delay"), \
             patch("bot.linkedin._close_open_chats"), \
             patch("bot.linkedin.time.sleep"), \
             patch("bot.linkedin._try_click", return_value=True):
            page = MagicMock()
            page.goto.return_value = None
            compose_loc = _make_visible_compose_loc()
            page.locator.return_value = compose_loc

            send_message(page, "https://linkedin.com/in/test", "Hi there!")

        page.keyboard.type.assert_called_once_with("Hi there!", delay=ANY)

    def test_send_button_found_via_js_evaluate_on_compose_box(self):
        """The send step must use compose_box.evaluate(), not _try_click."""
        evaluate_calls = []

        with patch("bot.linkedin._random_delay"), \
             patch("bot.linkedin._close_open_chats"), \
             patch("bot.linkedin.time.sleep"), \
             patch("bot.linkedin._try_click", return_value=True):
            page = MagicMock()
            page.goto.return_value = None
            compose_loc = MagicMock()
            compose_loc.first.wait_for.return_value = None
            compose_loc.first.is_visible.return_value = True
            compose_loc.first.evaluate.side_effect = lambda js: (
                evaluate_calls.append(js) or True
            )
            page.locator.return_value = compose_loc

            result = send_message(page, "https://linkedin.com/in/test", "Hi!")

        # At least one evaluate call must be the JS that looks for the send button
        send_js_calls = [c for c in evaluate_calls if "msg-form__send-button" in c]
        assert send_js_calls, "Expected a JS evaluate call targeting msg-form__send-button"
        assert result is True

    # ------------------------------------------------------------------
    # Lingering chat scenario — the original bug
    # ------------------------------------------------------------------

    def test_close_open_chats_called_before_message_button(self):
        """
        _close_open_chats must be called before clicking Message so any chat
        thread from a previous send is gone before we open the new dialog.
        This is the fix for the 'Could not click Send button' regression where
        .first was picking a Send button from an old off-screen chat thread.
        """
        call_order = []

        def record_close(page):
            call_order.append("close_chats")

        def record_try_click(page, selectors, timeout=5000):
            call_order.append("try_click")
            return True

        with patch("bot.linkedin._random_delay"), \
             patch("bot.linkedin.time.sleep"), \
             patch("bot.linkedin._close_open_chats", side_effect=record_close), \
             patch("bot.linkedin._try_click", side_effect=record_try_click):
            page = MagicMock()
            page.goto.return_value = None
            compose_loc = _make_visible_compose_loc()
            page.locator.return_value = compose_loc

            send_message(page, "https://linkedin.com/in/test", "Hi!")

        assert call_order[0] == "close_chats", (
            "_close_open_chats must run before the first _try_click"
        )

    def test_invisible_compose_box_is_skipped(self):
        """
        A compose box that is_visible() == False (off-screen chat thread) must
        be skipped.  The function must continue to the next selector or fail
        gracefully — never type into an invisible element.
        """
        with patch("bot.linkedin._random_delay"), \
             patch("bot.linkedin._close_open_chats"), \
             patch("bot.linkedin.time.sleep"), \
             patch("bot.linkedin._try_click", return_value=True):
            page = MagicMock()
            page.goto.return_value = None

            invisible_loc = MagicMock()
            invisible_loc.first.wait_for.return_value = None
            invisible_loc.first.is_visible.return_value = False  # off-screen thread
            page.locator.return_value = invisible_loc

            result = send_message(page, "https://linkedin.com/in/test", "Hi!")

        # No compose box found → returns False, never types
        assert result is False
        page.keyboard.type.assert_not_called()

    def test_ctrl_enter_fallback_when_js_send_fails(self):
        """
        If the JS evaluate for the send button returns False (button not found),
        fall back to Ctrl+Enter keyboard shortcut.
        """
        with patch("bot.linkedin._random_delay"), \
             patch("bot.linkedin._close_open_chats"), \
             patch("bot.linkedin.time.sleep"), \
             patch("bot.linkedin._try_click", return_value=True):
            page = MagicMock()
            page.goto.return_value = None

            compose_loc = MagicMock()
            compose_loc.first.wait_for.return_value = None
            compose_loc.first.is_visible.return_value = True
            # First evaluate call = scroll+focus (returns None), second = JS send (returns False)
            compose_loc.first.evaluate.side_effect = [None, False]
            page.locator.return_value = compose_loc

            result = send_message(page, "https://linkedin.com/in/test", "Hi!")

        page.keyboard.press.assert_called_with("Control+Return")
        assert result is True

    # ------------------------------------------------------------------
    # Failure paths
    # ------------------------------------------------------------------

    def test_returns_false_when_message_button_missing(self):
        with patch("bot.linkedin._random_delay"), \
             patch("bot.linkedin._close_open_chats"), \
             patch("bot.linkedin.time.sleep"), \
             patch("bot.linkedin._try_click", return_value=False):
            page = MagicMock()
            page.goto.return_value = None

            result = send_message(page, "https://linkedin.com/in/test", "Hello!")
        assert result is False

    def test_returns_false_when_compose_box_missing(self):
        with patch("bot.linkedin._random_delay"), \
             patch("bot.linkedin._close_open_chats"), \
             patch("bot.linkedin.time.sleep"), \
             patch("bot.linkedin._try_click", return_value=True):
            page = MagicMock()
            page.goto.return_value = None

            bad_loc = MagicMock()
            bad_loc.first.wait_for.side_effect = Exception("no compose")
            page.locator.return_value = bad_loc

            result = send_message(page, "https://linkedin.com/in/test", "Hello!")
        assert result is False

    def test_returns_false_when_both_send_paths_fail(self):
        """Returns False when JS send returns False AND Ctrl+Enter raises."""
        with patch("bot.linkedin._random_delay"), \
             patch("bot.linkedin._close_open_chats"), \
             patch("bot.linkedin.time.sleep"), \
             patch("bot.linkedin._try_click", return_value=True):
            page = MagicMock()
            page.goto.return_value = None
            page.keyboard.press.side_effect = Exception("keyboard dead")

            compose_loc = MagicMock()
            compose_loc.first.wait_for.return_value = None
            compose_loc.first.is_visible.return_value = True
            compose_loc.first.evaluate.side_effect = [None, False]  # scroll OK, send fails
            page.locator.return_value = compose_loc

            result = send_message(page, "https://linkedin.com/in/test", "Hi!")
        assert result is False

    def test_goto_exception_returns_false(self):
        page = MagicMock()
        page.goto.side_effect = Exception("network error")
        result = send_message(page, "https://linkedin.com/in/test", "Hello!")
        assert result is False

    def test_compose_click_failure_is_non_fatal(self):
        """If click() on the compose box fails, we continue via JS focus fallback."""
        with patch("bot.linkedin._random_delay"), \
             patch("bot.linkedin._close_open_chats"), \
             patch("bot.linkedin.time.sleep"), \
             patch("bot.linkedin._try_click", return_value=True):
            page = MagicMock()
            page.goto.return_value = None

            compose_loc = MagicMock()
            compose_loc.first.wait_for.return_value = None
            compose_loc.first.is_visible.return_value = True
            compose_loc.first.click.side_effect = Exception("outside viewport")
            compose_loc.first.evaluate.return_value = True
            page.locator.return_value = compose_loc

            result = send_message(page, "https://linkedin.com/in/test", "Hi!")
        assert result is True


# ---------------------------------------------------------------------------
# UMN_KEYWORDS constant
# ---------------------------------------------------------------------------

class TestUmnKeywords:
    def test_all_keywords_are_lowercase(self):
        for kw in UMN_KEYWORDS:
            assert kw == kw.lower(), f"Keyword '{kw}' is not lowercase"

    def test_has_at_least_four_variants(self):
        assert len(UMN_KEYWORDS) >= 4

    def test_contains_full_name(self):
        assert "university of minnesota" in UMN_KEYWORDS

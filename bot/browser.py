import os
import time
from playwright.sync_api import sync_playwright, BrowserContext, Page

SESSION_PATH = os.path.join(os.path.dirname(__file__), "..", "data", "session", "state.json")


def _launch_context(playwright, headless: bool = False) -> tuple:
    """Launch Chromium with a persistent-like context using saved session state."""
    browser = playwright.chromium.launch(headless=headless)

    if os.path.exists(SESSION_PATH):
        context = browser.new_context(storage_state=SESSION_PATH)
    else:
        context = browser.new_context()

    return browser, context


def login_and_save_session():
    """
    Opens a headed browser so the user can log in manually.
    Saves cookies/session to SESSION_PATH when done.
    """
    print("Opening browser for manual LinkedIn login...")
    print("Log in, complete any 2FA, then press ENTER here to save the session.")

    with sync_playwright() as p:
        browser, context = _launch_context(p, headless=False)
        page = context.new_page()
        page.goto("https://www.linkedin.com/login")
        input("  --> Press ENTER after you have fully logged in: ")
        os.makedirs(os.path.dirname(SESSION_PATH), exist_ok=True)
        context.storage_state(path=SESSION_PATH)
        print(f"Session saved to {SESSION_PATH}")
        browser.close()


def is_session_valid(page: Page) -> bool:
    """Quick check: are we still logged in?"""
    page.goto("https://www.linkedin.com/feed/", wait_until="domcontentloaded", timeout=30000)
    return "feed" in page.url or "linkedin.com/in/" in page.url


def get_browser_and_context(playwright):
    if not os.path.exists(SESSION_PATH):
        raise RuntimeError(
            "No saved session found. Run `python main.py login` first."
        )
    browser, context = _launch_context(playwright, headless=False)
    return browser, context

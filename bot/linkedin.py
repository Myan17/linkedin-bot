"""
LinkedIn DOM interactions: scrape connections, check education, send messages.

LinkedIn's DOM changes frequently. Each action uses multiple fallback selectors
and logs clearly so you can update selectors if LinkedIn pushes a UI change.
"""
import os
import time
import random
import logging
from datetime import datetime
from playwright.sync_api import Page, TimeoutError as PWTimeout

logger = logging.getLogger(__name__)

UMN_KEYWORDS = [
    "university of minnesota",
    "u of m",
    "umn",
    "u of mn",
]

# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _random_delay(min_secs: float = 3.0, max_secs: float = 7.0):
    delay = random.uniform(min_secs, max_secs)
    logger.debug(f"Sleeping {delay:.1f}s")
    time.sleep(delay)


def _message_delay():
    _random_delay(
        float(os.getenv("MESSAGE_DELAY_MIN_SECS", 45)),
        float(os.getenv("MESSAGE_DELAY_MAX_SECS", 90)),
    )


def _try_click(page: Page, selectors: list[str], timeout: int = 5000) -> bool:
    """Try a list of CSS/text selectors in order; return True on first success."""
    for sel in selectors:
        try:
            el = page.locator(sel).first
            el.wait_for(state="attached", timeout=timeout)
            # JS scrollIntoView works inside nested scroll containers where
            # Playwright's scroll_into_view_if_needed silently fails.
            el.evaluate("e => e.scrollIntoView({block: 'center', behavior: 'instant'})")
            time.sleep(0.3)
            el.click(force=True, timeout=timeout)
            return True
        except Exception:
            continue
    return False


def _safe_text(page: Page, selectors: list[str], default: str = "") -> str:
    for sel in selectors:
        try:
            el = page.locator(sel).first
            el.wait_for(timeout=4000)
            return el.inner_text().strip()
        except Exception:
            continue
    return default


# ---------------------------------------------------------------------------
# Scrape recent connections
# ---------------------------------------------------------------------------

CONNECTIONS_URL = "https://www.linkedin.com/mynetwork/invite-connect/connections/"


def dump_debug_info(page: Page):
    """Save a screenshot + HTML snippet to data/ for selector debugging."""
    import os
    debug_dir = os.path.join(os.path.dirname(__file__), "..", "data")
    os.makedirs(debug_dir, exist_ok=True)
    shot = os.path.join(debug_dir, "debug_screenshot.png")
    html = os.path.join(debug_dir, "debug_page.html")
    page.screenshot(path=shot, full_page=True)
    with open(html, "w", encoding="utf-8") as f:
        f.write(page.content())
    logger.info(f"Debug screenshot → {shot}")
    logger.info(f"Debug HTML       → {html}")


def scrape_recent_connections(page: Page, max_connections: int = 30) -> list[dict]:
    """
    Returns a list of dicts with keys: first_name, full_name, profile_url.

    Strategy: rather than relying on brittle class names (which LinkedIn changes
    frequently), we wait for the page to fully load then collect every unique
    /in/ profile link that appears inside a list item.  The name is read from
    the link's aria-label or surrounding text.
    """
    logger.info("Navigating to connections page...")
    page.goto(CONNECTIONS_URL, wait_until="load", timeout=45000)
    try:
        page.wait_for_selector("a[href*='/in/']", timeout=15000)
    except Exception:
        logger.warning("Timed out waiting for profile links.")
    _random_delay(2, 4)

    # Scroll to trigger lazy-loading
    for _ in range(3):
        page.keyboard.press("End")
        _random_delay(1.5, 3)

    # Dump every /in/ href on the page so we know exactly what exists
    all_hrefs = page.evaluate("""() =>
        [...document.querySelectorAll('a[href*="/in/"]')]
            .map(a => a.getAttribute('href'))
            .filter(Boolean)
    """)
    logger.debug(f"All /in/ hrefs on page: {all_hrefs}")

    # Use JavaScript — runs against the fully-rendered DOM
    raw = page.evaluate("""() => {
        const NAV_SKIP = [
            '/mynetwork/', '/jobs/', '/messaging/', '/notifications/',
            '/feed/', '/search/', '/learning/', '/premium/'
        ];

        // Find the logged-in user's own profile href to exclude it
        const meAnchors = [
            ...document.querySelectorAll('a[href*="/in/"]')
        ].filter(a => {
            const el = a.closest('nav') || a.closest('[class*="global-nav"]')
                     || a.closest('[class*="nav__me"]') || a.closest('header');
            return !!el;
        });
        const myHrefs = new Set(meAnchors.map(a => a.getAttribute('href').split('?')[0].replace(/\\/$/, '')));

        const seen = new Set();
        const results = [];

        document.querySelectorAll('a[href*="/in/"]').forEach(link => {
            const href = link.getAttribute('href') || '';
            if (!href.includes('/in/')) return;
            if (NAV_SKIP.some(f => href.includes(f))) return;

            const clean = href.split('?')[0].replace(/\\/$/, '');
            if (myHrefs.has(clean)) return;
            if (seen.has(clean)) return;
            seen.add(clean);

            const url = clean.startsWith('http') ? clean : 'https://www.linkedin.com' + clean;

            // Walk up the DOM to find the card, read the name
            const card = link.closest('li') || link.closest('[class*="card"]') || link.parentElement;
            let name = link.getAttribute('aria-label') || '';

            if (!name && card) {
                const nameEl = card.querySelector('[class*="name"], [class*="actor"], span[dir="ltr"], strong, h3, h4');
                if (nameEl) name = nameEl.textContent.trim();
            }
            if (!name && card) {
                name = (card.innerText || '').trim().split('\\n').map(s => s.trim()).filter(Boolean)[0] || '';
            }
            if (!name) name = link.innerText.trim().split('\\n')[0].trim();

            results.push({ profile_url: url, full_name: name.trim() });
        });

        return results;
    }""")

    logger.debug(f"JS raw results: {raw}")

    connections = []
    for item in raw[:max_connections]:
        raw_name = item.get("full_name", "").strip()
        profile_url = item.get("profile_url", "").strip()
        if not raw_name or not profile_url:
            continue

        # Clean name: strip leading emoji/symbols, take only the real name
        # (stop at comma or pipe — everything after is job title/suffix)
        clean = raw_name.split(",")[0].split("|")[0].strip()
        # Drop leading non-letter characters (e.g. ✅, 🔥)
        clean = clean.lstrip("".join(c for c in clean if not c.isalpha() and c != " ")).strip()
        if not clean:
            clean = raw_name

        words = clean.split()
        first_name = words[0] if words else clean
        # Search name: first + last name only (skip middle names / suffixes)
        search_name = " ".join(words[:2]) if len(words) >= 2 else clean

        connections.append({
            "first_name": first_name,
            "full_name": search_name,   # used for To: field search
            "display_name": raw_name,   # kept for logging
            "profile_url": profile_url,
        })

    logger.info(f"Found {len(connections)} connection cards")
    return connections


# ---------------------------------------------------------------------------
# UMN student detection
# ---------------------------------------------------------------------------

def is_umn_student(page: Page, profile_url: str) -> bool:
    """Visit the profile and scan the Education section for UMN keywords."""
    logger.info(f"Checking education for {profile_url}")
    try:
        page.goto(profile_url, wait_until="domcontentloaded", timeout=30000)
        _random_delay(2, 4)

        # Try to expand the Education section if collapsed
        _try_click(page, [
            "section#education ~ div button",
            "button[aria-label*='education']",
        ])
        _random_delay(1, 2)

        edu_text = _safe_text(page, [
            "section#education",
            "section[data-section='education']",
            "#education",
        ], default="").lower()

        # Also grab full page text as fallback (slower but more resilient)
        if not edu_text:
            edu_text = page.inner_text("body").lower()

        for keyword in UMN_KEYWORDS:
            if keyword in edu_text:
                logger.info(f"  -> UMN student detected ({keyword})")
                return True

        return False

    except Exception as e:
        logger.warning(f"Could not check education for {profile_url}: {e}")
        return False  # err on side of not skipping


# ---------------------------------------------------------------------------
# Send a message to a connection
# ---------------------------------------------------------------------------

def _close_open_chats(page: Page):
    """
    Close all open bottom chat-bubble panels via JavaScript.

    LinkedIn's SPA keeps chat threads alive across page navigations. Without
    this, each profile visit accumulates more msg-form__contenteditable and
    msg-form__send-button elements in the DOM. Because we use .first, we end
    up targeting a button from an old (off-screen) thread instead of the new
    message dialog — causing viewport errors and send failures.

    We use page.evaluate instead of CSS selectors because LinkedIn's class
    names change frequently; aria-label is far more stable.
    """
    try:
        page.evaluate("""() => {
            document.querySelectorAll(
                '.msg-overlay-conversation-bubble button[aria-label*="Close"],'
                + '.msg-overlay-list-bubble button[aria-label*="Close"],'
                + '.msg-overlay-bubble-header button[aria-label*="Close"],'
                + 'button[data-control-name="overlay.close_conversation_window"]'
            ).forEach(b => { try { b.click(); } catch(e) {} });
        }""")
        time.sleep(0.5)
    except Exception:
        pass


def send_message(page: Page, profile_url: str, message_text: str, recipient_name: str = "", full_name: str = "") -> bool:
    """
    Navigate to the connection's profile, open the message dialog, type and send.

    Key design decisions:
    - _close_open_chats() before each send so there is only ONE compose box
      and ONE send button in the DOM at any time.
    - page.keyboard.type() instead of locator.type() per character: React's
      synthetic-event system detects keyboard input correctly this way, which
      is required to enable the Send button.
    - Send button is found via JavaScript scoped to the same dialog container
      as the compose box — never globally with .first — so a lingering chat
      thread from a previous send can never interfere.
    - Ctrl+Enter keyboard shortcut as a final fallback.
    """
    logger.info(f"Sending message to {profile_url}")
    try:
        page.goto(profile_url, wait_until="domcontentloaded", timeout=30000)
        _random_delay(2, 5)

        # Purge any chat threads left open from previous sends before we open
        # a new one — keeps exactly one compose box in the DOM.
        _close_open_chats(page)
        _random_delay(0.5, 1.0)

        # Click the Message button on their profile
        clicked = _try_click(page, [
            "button.message-anywhere-button",
            "a[href*='messaging/thread']",
            "button[aria-label*='Message']",
            "button:has-text('Message')",
        ])

        if not clicked:
            logger.error(f"Could not find Message button on {profile_url}")
            return False

        _random_delay(1, 2)

        # Wait for the New Message dialog to appear
        try:
            page.wait_for_selector(".msg-connections-typeahead, .msg-form__contenteditable", timeout=8000)
        except Exception:
            pass

        # ----------------------------------------------------------------
        # Fill in the To: recipient field if present
        # ----------------------------------------------------------------
        to_input_selectors = [
            "input.msg-connections-typeahead__search-input",
            "input[placeholder*='name']",
            "input[aria-label*='recipient']",
            ".msg-connections-typeahead input",
        ]

        to_input = None
        for sel in to_input_selectors:
            try:
                el = page.locator(sel).first
                el.wait_for(timeout=3000)
                to_input = el
                break
            except Exception:
                continue

        search_name = full_name or recipient_name
        if to_input and search_name:
            logger.info(f"  Filling To: field with '{search_name}'")
            to_input.click()
            _random_delay(0.3, 0.7)
            to_input.type(search_name, delay=random.randint(50, 120))
            _random_delay(2, 3)

            suggestion_selectors = [
                "li.msg-connections-typeahead__result-item",
                ".msg-connections-typeahead__result-item",
                "li[data-control-name='compose_message_connection']",
                "ul.msg-connections-typeahead__results li",
                "div[role='option']",
                "li[role='option']",
            ]
            selected = _try_click(page, suggestion_selectors, timeout=5000)
            if not selected:
                page.keyboard.press("Enter")
            _random_delay(0.5, 1)

        # ----------------------------------------------------------------
        # Locate compose box — prefer the active dialog, skip invisible ones
        # ----------------------------------------------------------------
        compose_selectors = [
            "div.msg-overlay-conversation-bubble--is-active div.msg-form__contenteditable",
            "div.msg-overlay-list-bubble div.msg-form__contenteditable",
            "div.msg-form__contenteditable",
            "div[contenteditable='true'][aria-label*='Write']",
            "div[contenteditable='true'][aria-label*='message']",
            "div[role='textbox']",
        ]

        compose_box = None
        for sel in compose_selectors:
            try:
                el = page.locator(sel).first
                el.wait_for(timeout=8000)
                if not el.is_visible():
                    continue
                compose_box = el
                break
            except Exception:
                continue

        if not compose_box:
            logger.error("Could not find compose box")
            return False

        # Scroll into view and focus via JS — more reliable than Playwright's
        # scroll_into_view_if_needed when the element is inside a nested container.
        compose_box.evaluate("el => { el.scrollIntoView({block: 'center', behavior: 'instant'}); el.focus(); }")
        _random_delay(0.3, 0.7)
        try:
            compose_box.click(timeout=5000)
        except Exception:
            pass  # focus was already set via JS above
        _random_delay(0.5, 1.0)

        # Type via page.keyboard so React's synthetic events fire correctly,
        # enabling the Send button. Per-character locator.type() can miss events.
        page.keyboard.type(message_text, delay=random.randint(30, 80))
        _random_delay(1, 3)

        # ----------------------------------------------------------------
        # Send: find the button relative to the compose box's container so
        # we never target a Send button from another open chat thread.
        # ----------------------------------------------------------------
        sent = False
        try:
            sent = bool(compose_box.evaluate("""el => {
                const container = el.closest('.msg-overlay-conversation-bubble')
                               || el.closest('.msg-overlay-list-bubble')
                               || el.closest('[role="dialog"]')
                               || el.closest('form')
                               || el.parentElement;
                if (!container) return false;
                const btn = container.querySelector(
                    'button.msg-form__send-button, button[aria-label="Send"]'
                );
                if (btn) { btn.click(); return true; }
                return false;
            }"""))
        except Exception:
            pass

        if not sent:
            # Ctrl+Enter is LinkedIn's keyboard shortcut for sending a message
            logger.debug("  JS send failed, falling back to Ctrl+Enter")
            try:
                page.keyboard.press("Control+Return")
                sent = True
            except Exception:
                pass

        if not sent:
            logger.error("Could not send message")
            return False

        _random_delay(1, 2)
        logger.info(f"  -> Message sent successfully to {profile_url}")
        return True

    except Exception as e:
        logger.error(f"Error sending message to {profile_url}: {e}")
        return False

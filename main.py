#!/usr/bin/env python3
"""
LinkedIn Outreach Bot
Usage:
  python main.py save-credentials  — store LinkedIn email+password in macOS Keychain
  python main.py login             — one-time browser login, saves session
  python main.py run               — full bot cycle
  python main.py run --dry-run     — preview actions without sending
  python main.py status            — print DB summary
  python main.py debug             — save screenshot + HTML of connections page for diagnosis
  python main.py delete-credentials — remove credentials from Keychain
"""
import sys
import os
import logging
from datetime import datetime
from dotenv import load_dotenv

load_dotenv()

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(message)s",
    handlers=[
        logging.StreamHandler(sys.stdout),
        logging.FileHandler(
            os.path.join(os.path.dirname(__file__), "data", "bot.log"),
            encoding="utf-8",
        ),
    ],
)
logger = logging.getLogger(__name__)


def cmd_debug():
    from playwright.sync_api import sync_playwright
    from bot.browser import get_browser_and_context
    from bot.linkedin import CONNECTIONS_URL, dump_debug_info, scrape_recent_connections
    logger.info("Debug: loading connections page and saving snapshot...")
    with sync_playwright() as p:
        browser, context = get_browser_and_context(p)
        page = context.new_page()
        page.goto(CONNECTIONS_URL, wait_until="load", timeout=45000)
        page.wait_for_selector("a[href*='/in/']", timeout=15000)
        dump_debug_info(page)
        connections = scrape_recent_connections(page)
        logger.info(f"Parsed {len(connections)} connections:")
        for c in connections:
            logger.info(f"  {c['full_name']} → {c['profile_url']}")
        browser.close()


def cmd_save_credentials():
    from bot.credentials import save_credentials
    save_credentials()


def cmd_delete_credentials():
    from bot.credentials import delete_credentials
    delete_credentials()


def cmd_login():
    from bot.credentials import credentials_exist
    from bot.browser import login_and_save_session
    if not credentials_exist():
        print("No credentials found. Run `python main.py save-credentials` first.")
        sys.exit(1)
    login_and_save_session()


def cmd_status():
    from bot.database import init_db, get_stats
    init_db()
    stats = get_stats()
    if not stats:
        print("No connections tracked yet.")
        return
    total = sum(stats.values())
    print(f"\n{'Status':<20} {'Count':>6}")
    print("-" * 28)
    for status, count in sorted(stats.items()):
        print(f"{status:<20} {count:>6}")
    print("-" * 28)
    print(f"{'TOTAL':<20} {total:>6}\n")


def cmd_run(dry_run: bool = False):
    from playwright.sync_api import sync_playwright
    from bot.browser import get_browser_and_context, is_session_valid
    from bot.database import (
        init_db, upsert_connection, mark_umn_student,
        mark_initial_sent, mark_followup_sent,
        get_pending_initial, get_pending_followup,
    )
    from bot.linkedin import (
        scrape_recent_connections, is_umn_student, send_message,
    )
    from bot.templates import initial_message, followup_message
    from bot.scheduler import compute_followup_date

    max_initial = int(os.getenv("MAX_INITIAL_MSGS_PER_RUN", 5))
    max_followup = int(os.getenv("MAX_FOLLOWUP_MSGS_PER_RUN", 3))
    window_hours = int(os.getenv("CONNECTION_WINDOW_HOURS", 2))

    init_db()
    mode = "[DRY RUN] " if dry_run else ""

    with sync_playwright() as p:
        browser, context = get_browser_and_context(p)
        page = context.new_page()

        # Verify session is still valid
        if not is_session_valid(page):
            logger.error("Session expired. Run `python main.py login` to refresh.")
            browser.close()
            sys.exit(1)

        # ----------------------------------------------------------------
        # Step 1: Scrape new connections
        # ----------------------------------------------------------------
        logger.info(f"{mode}Scraping recent connections...")
        connections = scrape_recent_connections(page)
        new_count = 0
        for conn in connections:
            added = upsert_connection(conn["profile_url"], conn["first_name"], conn["full_name"])
            if added:
                new_count += 1
                logger.info(f"  New connection tracked: {conn.get('display_name', conn['full_name'])} ({conn['profile_url']})")
        logger.info(f"Scraped {len(connections)} connections, {new_count} new.")

        # ----------------------------------------------------------------
        # Step 2: Check new connections for UMN and filter
        # ----------------------------------------------------------------
        pending = get_pending_initial(window_hours=window_hours, limit=max_initial * 2)
        logger.info(f"{mode}Checking {len(pending)} pending connection(s) for UMN filter...")
        for conn in pending:
            if is_umn_student(page, conn["linkedin_profile_url"]):
                if not dry_run:
                    mark_umn_student(conn["linkedin_profile_url"])
                logger.info(f"  Skipping UMN student: {conn['full_name']}")

        # ----------------------------------------------------------------
        # Step 3: Send initial messages
        # ----------------------------------------------------------------
        to_message = get_pending_initial(window_hours=window_hours, limit=max_initial)
        logger.info(f"{mode}Sending initial messages to {len(to_message)} connection(s)...")

        for conn in to_message:
            msg = initial_message(conn["first_name"])
            if dry_run:
                logger.info(
                    f"  [DRY RUN] Would send to {conn['full_name']}:\n"
                    + "\n    ".join(msg.splitlines())
                )
                continue

            success = send_message(page, conn["linkedin_profile_url"], msg, recipient_name=conn["first_name"], full_name=conn["full_name"])
            if success:
                followup_due = compute_followup_date(datetime.now())
                mark_initial_sent(conn["linkedin_profile_url"], followup_due)
                logger.info(f"  Initial message sent. Follow-up due: {followup_due.date()}")
            else:
                logger.warning(f"  Failed to send to {conn['full_name']}, will retry next run.")

            from bot.linkedin import _message_delay
            _message_delay()

        # ----------------------------------------------------------------
        # Step 4: Send follow-ups
        # ----------------------------------------------------------------
        followups = get_pending_followup(limit=max_followup)
        logger.info(f"{mode}Sending follow-up messages to {len(followups)} connection(s)...")

        for conn in followups:
            msg = followup_message(conn["first_name"])
            if dry_run:
                logger.info(
                    f"  [DRY RUN] Would follow-up {conn['full_name']}:\n"
                    + "\n    ".join(msg.splitlines())
                )
                continue

            success = send_message(page, conn["linkedin_profile_url"], msg, recipient_name=conn["first_name"], full_name=conn["full_name"])
            if success:
                mark_followup_sent(conn["linkedin_profile_url"])
                logger.info(f"  Follow-up sent to {conn['full_name']}")
            else:
                logger.warning(f"  Follow-up failed for {conn['full_name']}, will retry next run.")

            from bot.linkedin import _message_delay
            _message_delay()

        browser.close()

    logger.info("Run complete.")


def main():
    args = sys.argv[1:]

    if not args or args[0] == "help":
        print(__doc__)
        return

    command = args[0]

    if command == "debug":
        cmd_debug()
    elif command == "save-credentials":
        cmd_save_credentials()
    elif command == "delete-credentials":
        cmd_delete_credentials()
    elif command == "login":
        cmd_login()
    elif command == "status":
        cmd_status()
    elif command == "run":
        dry_run = "--dry-run" in args
        cmd_run(dry_run=dry_run)
    else:
        print(f"Unknown command: {command}")
        print(__doc__)
        sys.exit(1)


if __name__ == "__main__":
    main()

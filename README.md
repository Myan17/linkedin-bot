# LinkedIn Outreach Bot

[![CI](https://github.com/Myan17/linkedin-bot/actions/workflows/ci.yml/badge.svg)](https://github.com/Myan17/linkedin-bot/actions/workflows/ci.yml)

Automates personalized LinkedIn outreach to recent connections using Playwright. Filters out University of Minnesota students, sends templated initial messages, and schedules follow-ups.

## How it works

1. **Scrapes** your 30 most recent connections
2. **Filters** UMN students by visiting each profile's Education section
3. **Messages** remaining connections with a personalized initial message
4. **Follows up** automatically 7 days later (adjusted for weekends)

All state is stored in a local SQLite database (`data/connections.db`).

## Security and scope

- **Credentials never touch disk.** They are read with `getpass` (no terminal
  echo) and stored only in the macOS Keychain via `keyring`. `.env` holds
  profile text, not secrets. `data/` — the SQLite DB and the browser session
  cookies — is gitignored. Tests assert that saving credentials writes nothing
  to the working directory and never prints the password.
- **Missing credentials fail closed** with the command that fixes them, rather
  than attempting a login with `None`.
- **Rate-limited by design:** capped messages per run and a randomized 45–90 s
  delay between sends, configurable in `.env`.
- CI runs a **gitleaks** scan over full history on every push.
- **This is a local tool and is deliberately not deployed.** LinkedIn's User
  Agreement prohibits automated access, so running it at all carries account
  risk. It exists as an engineering exercise in browser automation, state
  management and scheduling — not as a hosted service.

## Testing

```bash
pip install -r requirements.txt pytest
pytest tests -q
```

97 tests, 72% coverage, gated at 65% in CI. No test launches a browser or
contacts LinkedIn — Playwright pages are stubbed.

| Suite | Covers |
|---|---|
| `test_linkedin.py` | connection scraping, UMN education filter, message sending, selector fallbacks |
| `test_database.py` | connection state, dedup, follow-up bookkeeping |
| `test_scheduler.py` | 7-day follow-up with weekend adjustment |
| `test_templates.py` | message rendering from `.env` profile fields |
| `test_credentials.py` | keychain-only storage, `getpass` for the password, no stdout leak, fail-closed getters, idempotent delete |

## Prerequisites

- Python 3.11+
- macOS (uses Keychain for credential storage)
- A LinkedIn account

## Setup

```bash
# 1. Clone and create virtualenv
git clone https://github.com/YOUR_USERNAME/linkedin-bot
cd linkedin-bot
python -m venv venv
source venv/bin/activate

# 2. Install dependencies (includes Playwright browsers)
pip install -r requirements.txt
playwright install chromium

# 3. Configure environment
cp .env.example .env
# Edit .env and set RESUME_LINK to your hosted resume URL

# 4. Save LinkedIn credentials to Keychain
python main.py save-credentials

# 5. One-time browser login (handles 2FA)
python main.py login
```

## Usage

```bash
# Full run — scrape, filter, and send messages
python main.py run

# Preview what would be sent without actually sending
python main.py run --dry-run

# Show DB summary (how many sent, pending, follow-ups due)
python main.py status

# Save a debug screenshot + HTML of the connections page
python main.py debug
```

## Configuration

Set these in `.env` (all optional — defaults shown):

| Variable | Default | Description |
|---|---|---|
| `RESUME_LINK` | — | URL to your hosted resume |\n| `GITHUB_URL` | — | URL to your GitHub profile |\n| `SCHOOL` | — | Your university name |\n| `MAJOR` | `Computer Science` | Your major |\n| `YEAR` | `senior` | Your year (freshman, junior, etc.) |\n| `ROLE` | `software engineering` | Role type you are targeting |
| `MAX_INITIAL_MSGS_PER_RUN` | `5` | Cap on initial messages per run |
| `MAX_FOLLOWUP_MSGS_PER_RUN` | `3` | Cap on follow-ups per run |
| `CONNECTION_WINDOW_HOURS` | `2` | Only message connections added in this window |
| `MESSAGE_DELAY_MIN_SECS` | `45` | Min delay between messages |
| `MESSAGE_DELAY_MAX_SECS` | `90` | Max delay between messages |

## Running tests

```bash
venv/bin/python -m pytest tests/ -v
```

## Project structure

```
bot/
  linkedin.py     # Playwright DOM interactions (scrape, filter, send)
  browser.py      # Browser/session management
  database.py     # SQLite persistence
  templates.py    # Message templates
  scheduler.py    # Follow-up date calculation
  credentials.py  # macOS Keychain helpers
tests/
  test_linkedin.py
main.py           # CLI entry point
```

## Notes

- Session cookies are saved to `data/session/state.json` — re-run `python main.py login` if LinkedIn logs you out
- The bot runs in a headed (visible) browser so LinkedIn's bot detection is less likely to trigger
- Credentials (email/password) are stored in macOS Keychain, never in files

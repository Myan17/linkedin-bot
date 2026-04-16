# LinkedIn Outreach Bot

Automates personalized LinkedIn outreach to recent connections using Playwright. Filters out University of Minnesota students, sends templated initial messages, and schedules follow-ups.

## How it works

1. **Scrapes** your 30 most recent connections
2. **Filters** UMN students by visiting each profile's Education section
3. **Messages** remaining connections with a personalized initial message
4. **Follows up** automatically 7 days later (adjusted for weekends)

All state is stored in a local SQLite database (`data/connections.db`).

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

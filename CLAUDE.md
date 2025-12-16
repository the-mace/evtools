# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## Project Overview

evtools is a Python collection for monitoring Tesla, Rivian, and SolarCity/Tesla Solar systems. The tools interact with unofficial APIs to track vehicle state, solar production, and post automated updates to Twitter. This is primarily a personal monitoring/automation suite used via cron jobs.

## Build and Installation

```bash
# Build and install the package
python3 setup.py sdist && pip install dist/evtools-1.0.2.tar.gz

# Install dependencies
pip install -r requirements.txt
```

## Core Modules

### Main Command-Line Tools

Three main tools provide the primary functionality:

- **tesla.py** - Tesla vehicle monitoring via TeslaPy library
- **rivian.py** - Rivian vehicle monitoring via rivian-python-api
- **solarcity.py** - Tesla Solar production monitoring via web scraping

Each tool supports `--help` for full option documentation.

### Helper Modules

- **tl_email.py** - Email notifications via SMTP (configurable via TL_SMTP_* env vars)
- **tl_weather.py** - Weather data integration using WeatherAPI (requires WEATHERAPI_API_KEY)
- **tl_tweets.py** - Twitter integration for automated posting
- **tl_stock.py** - Stock-related utilities

## Architecture

### Authentication Pattern

All tools use environment variables for credentials and configuration. Never hardcode sensitive data.

**Tesla authentication:**
- Uses TeslaPy with custom Selenium-based auth (`custom_auth()` in tesla.py)
- Stores tokens in DATA_FILE (default: tesla.json)
- Requires TESLA_EMAIL, TESLA_CAR_NAME environment variables

**Rivian authentication:**
- Uses rivian_auth.pickle file created externally by Rivian CLI
- Requires RIVIAN_EMAIL, RIVIAN_VEHICLE_ID, DISCORD_URL environment variables
- Authentication state restored via `restore_state()` function

**Solar authentication:**
- Web scraping approach using Selenium WebDriver
- Requires SOLARCITY_USER, SOLARCITY_SITE_ID environment variables

### State Management

All tools follow the same pattern:
1. Single-instance locking via fcntl on /tmp/*.lock files
2. JSON-based persistent storage (tesla.json, rivian.json, solarcity.json)
3. `load_data()` and `save_data()` functions handle serialization
4. Atomic file writes using .tmp rename pattern

### Data Files

- **DATA_FILE** - Main state database (JSON format)
  - daily_state_am/daily_state_pm - Historical vehicle/solar state
  - config - Last tweet times, firmware versions
  - mileage_tweet - Milestone tracking
- **SLEEP_LOG_FILE** - CSV logs for vehicle sleep monitoring
- **DUMP_DIR** - Full API response dumps for debugging

### Sleep Management (Tesla)

The Tesla tool implements sophisticated sleep management to avoid keeping the vehicle awake:
- Tracks `last_poke` timestamp to limit wake frequency (MIN_TIME_BETWEEN_POKES = 58 minutes)
- `get_vehicle_data()` intelligently decides whether to poll based on vehicle state
- `sleep_check()` monitors vehicle state without forcing wake

### Error Handling

All main tools implement:
- Retry logic with MAX_RETRIES (default: 3)
- Exception email notifications via `mail_exception()`
- DEBUG_MODE flag to prevent actual tweets/emails during testing

## Environment Variables

### Required Variables
```bash
# Tesla
export TESLA_EMAIL="your-email@example.com"
export TESLA_CAR_NAME="Your Car Name"
export TESLA_LOGFILE="~/logs/tesla.log"

# Rivian
export RIVIAN_EMAIL="your-email@example.com"
export RIVIAN_VEHICLE_ID="your-vehicle-id"
export RIVIAN_LOGFILE="~/logs/rivian.log"
export DISCORD_URL="your-discord-webhook-url"

# SolarCity
export SOLARCITY_USER="your-email@example.com"
export SOLARCITY_SITE_ID="your-site-id"

# Weather
export WEATHERAPI_API_KEY="your-api-key"

# Email (optional, defaults to localhost:25)
export TL_SMTP_SERVER="smtp.example.com"
export TL_SMTP_PORT="587"
export TL_SMTP_USER="username"
export TL_SMTP_PASSWORD="password"
export TL_MAILFROM="sender@example.com"
```

### Optional Variables
```bash
export TESLA_DEBUG_MODE=1  # Prevents actual tweets/data writes
export RIVIAN_DEBUG_MODE=1
export TESLA_DATA_FILE="custom_path.json"
export TESLA_SLEEP_LOG_FILE="custom_sleep_log.csv"
export TESLA_PICTURES_PATH="path/to/images"
```

## Common Tasks

### Testing Changes

Always set DEBUG_MODE=1 when testing to prevent actual tweets and data modifications:
```bash
export TESLA_DEBUG_MODE=1
./tesla.py --status
```

### Monitoring Vehicle State

```bash
# Check current status
./tesla.py --status
./rivian.py --status

# Monitor sleep state (for power optimization)
./tesla.py --sleepcheck
./rivian.py --sleepcheck

# Check if plugged in
./tesla.py --pluggedin
./rivian.py --pluggedin
```

### Data Collection

```bash
# Save current state snapshot (use with cron)
./tesla.py --state
./rivian.py --state

# Check mileage and tweet milestones
./tesla.py --mileage
./rivian.py --mileage

# Check for firmware updates
./tesla.py --firmware
./rivian.py --firmware
```

### Solar Monitoring

```bash
# Daily generation report
./solarcity.py --daily

# Weekly summary
./solarcity.py --report

# Monthly summary (auto-detects last day of month)
./solarcity.py --monthly

# Export all data
./solarcity.py --export
```

## Cron Integration

These tools are designed for cron automation. Example crontab entries:

```cron
# Tesla monitoring (every hour during day)
0 8-22 * * * source ~/.bashrc; cd ~/Documents/Data; python ~/Documents/Code/evtools/tesla.py --state

# Check if plugged in at night
0 22 * * * source ~/.bashrc; cd ~/Documents/Data; python ~/Documents/Code/evtools/tesla.py --pluggedin

# Solar daily report
0 21 * * * source ~/.bashrc; cd ~/Documents/Data; python ~/Documents/Code/evtools/solarcity.py --daily
```

## Code Conventions

- Use rotating log handlers (RotatingFileHandler, 5MB max, 8 backups)
- Log at INFO level for normal operations, DEBUG for detailed tracing
- All timestamps use datetime module, stored as ISO format or YYYYMMDD strings
- File locking prevents concurrent execution
- Atomic writes for data files (write to .tmp, then rename)

## Testing

There are no automated unit tests. Test manually with DEBUG_MODE=1 and verify:
1. No actual API calls are made that change state
2. No tweets are posted
3. No data files are modified
4. Log output shows expected behavior

## Dependencies

Key external dependencies:
- **TeslaPy** - Tesla API wrapper (version 2.8.0)
- **rivian-python-api** - Rivian API wrapper (from github.com/the-mace/rivian-python-api)
- **selenium** - Web automation for authentication and scraping (4.0.0)
- **tweepy** - Twitter API client (4.14.0)
- **beautifulsoup4** - HTML parsing for SolarCity scraping

## Known Issues

- SolarCity scraping depends on Tesla's web UI structure which can break with updates
- Tesla sleep management is conservative to avoid phantom drain
- Weather API switched from Dark Sky to WeatherAPI after Apple acquisition
- Rivian authentication requires pre-existing pickle file from separate CLI tool

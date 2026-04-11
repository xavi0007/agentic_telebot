# 🤖 Agentic Telegram Calendar Bot

A fully agentic Telegram bot powered by Claude that manages your Apple Calendar through natural language.

## How It Works

```
You (Telegram) → Bot → Claude (thinks + picks tools) → Apple Calendar → Claude (summarizes) → You
```

Claude uses a **tool-use agentic loop**: it decides which calendar functions to call, executes them, reads the results, and replies — all automatically.

---

## Setup

### 1. Get a Telegram Bot Token
- Open Telegram → search `@BotFather`
- Send `/newbot` and follow prompts
- Copy your **bot token**

### 2. Get an Anthropic API Key
- Go to https://console.anthropic.com
- Create an API key

### 3. Install dependencies (macOS required for Apple Calendar)
```bash
pip install -r requirements.txt
```

### 4. Set environment variables
```bash
export TELEGRAM_TOKEN="your-telegram-token"
export ANTHROPIC_API_KEY="your-anthropic-key"
export TIMEZONE="Asia/Singapore"   # or your local timezone
```

### 5. Run
```bash
python bot.py
```

> **First run**: macOS will prompt you to grant Calendar access. Allow it in System Settings → Privacy → Calendar.

---

## Usage

| Say...                                          | What happens                        |
|-------------------------------------------------|-------------------------------------|
| "What's on my calendar this week?"             | Reads next 7 days of events         |
| "Add dentist tomorrow at 3pm"                  | Creates event Apr X 3–4pm           |
| "Schedule team lunch Friday 12:30–1:30pm"      | Creates event with exact times      |
| "Delete the dentist appointment"               | Fetches events, finds + deletes it  |
| "What calendars do I have?"                    | Lists all Apple Calendar names      |
| "Add a reminder on April 5 at 6am for my flight" | Creates morning event              |

Commands:
- `/start` — Welcome
- `/clear` — Reset memory
- `/help` — Help

---

## Architecture

```
bot.py
 ├── Telegram handlers    (python-telegram-bot)
 ├── Agentic loop         (Claude claude-sonnet-4-6 + tool_use)
 │    ├── add_calendar_event
 │    ├── get_upcoming_events
 │    ├── delete_calendar_event
 │    └── list_calendars
 └── Apple Calendar API   (EventKit via pyobjc)
```

### Key agentic loop (in `run_agent()`):
1. User message + history → Claude
2. Claude returns `tool_use` block → execute the function
3. Return result to Claude → Claude decides next step
4. Repeat until Claude returns `end_turn` (final answer)

---

## Running on Linux / Deploying to a Server

Apple Calendar (EventKit) is macOS-only. For servers, replace the calendar tool functions with:
- **Google Calendar API** (`google-api-python-client`)
- **CalDAV** (`caldav` library)

The agentic loop and Telegram integration stays identical — just swap the tool implementations.

---

## Keeping History

The bot stores per-user conversation history in memory (`user_sessions` dict). For production, persist this to Redis or SQLite so history survives restarts.

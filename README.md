# 🤖 Telegram Calendar Bot

A Telegram bot powered by DeepSeek LLM that manages your iCloud calendar via CalDAV. Hosted on fly.io.

## How It Works

```
You (Telegram) → Bot → DeepSeek (extracts event details) → CalDAV → iCloud Calendar
```

The bot listens to your messages, uses DeepSeek to extract calendar event information, and automatically creates/deletes events in your iCloud calendar.

---

## Setup

### 1. Get a Telegram Bot Token
- Open Telegram → search `@BotFather`
- Send `/newbot` and follow prompts
- Copy your **bot token**

### 2. Get a DeepSeek API Key
- Go to https://platform.deepseek.com
- Create an API key

### 3. Get iCloud Credentials
- Your Apple ID email as `ICLOUD_USER`
- An [app-specific password](https://support.apple.com/en-us/102654) as `ICLOUD_APP_PASS`
- Have a calendar named "Agentic" in iCloud, make it available for public.

### 4. Local Development
```bash
pip install -r requirements.txt
export TELEGRAM_TOKEN="your-token"
export DEEPSEEK_API_KEY="your-key"
export ICLOUD_USER="your@icloud.com"
export ICLOUD_APP_PASS="your-app-specific-password"
python bot.py
```

### 5. Deploy to fly.io
```bash
flyctl launch
flyctl secrets set TELEGRAM_TOKEN="..." DEEPSEEK_API_KEY="..." ICLOUD_USER="..." ICLOUD_APP_PASS="..."
flyctl deploy
```

---

## Usage

Just send natural language messages to your bot:

| Message                           | Result                              |
|-----------------------------------|-------------------------------------|
| "Add meeting tomorrow at 3pm"     | Creates event in iCloud calendar    |
| "Schedule lunch Friday 12-1pm"    | Creates event with title & time     |
| "/delete meeting"                 | Deletes event matching keyword      |

---

## Architecture

```
bot.py
 ├── Telegram message handler  (python-telegram-bot)
 ├── LLM event extraction      (DeepSeek API)
 ├── Calendar operations       (CalDAV/iCloud)
 └── HTTP health check         (Port 8080 for fly.io)
```

### Event Flow:
1. User sends message to Telegram bot
2. DeepSeek extracts event details (title, date, time, location)
3. Bot creates event in iCloud via CalDAV
4. Bot confirms to user

### Delete Flow:
1. User sends `/delete <keyword>`
2. Bot searches iCloud calendar for matching event
3. Bot deletes matching event
4. Bot confirms deletion

---

## Environment Variables

| Variable | Required | Description |
|----------|----------|-------------|
| `TELEGRAM_TOKEN` | Yes | Telegram bot token from @BotFather |
| `DEEPSEEK_API_KEY` | Yes | DeepSeek API key |
| `ICLOUD_USER` | Yes | Apple ID email |
| `ICLOUD_APP_PASS` | Yes | App-specific password from Apple ID |

---

## Deployment Notes

- **Platform**: fly.io (Singapore region)
- **HTTP Server**: Runs on port 8080 for health checks
- **Calendar**: Uses CalDAV to sync with iCloud (works from any OS)
- **Polling**: Bot uses long polling (no webhook setup required)

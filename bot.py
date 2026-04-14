from http.server import HTTPServer, BaseHTTPRequestHandler
import threading
from telegram.ext import CommandHandler
import os
import re
from telegram import Update
from telegram.ext import ApplicationBuilder, MessageHandler, filters, ContextTypes
from openai import OpenAI
import caldav
from datetime import datetime, UTC
import json
from dotenv import load_dotenv
from datetime import datetime, timedelta
from caldav.elements import dav
import uuid


load_dotenv()  # reads variables from a .env file and sets them in os.environ

TELEGRAM_TOKEN = os.environ["TELEGRAM_TOKEN"]
DEEPSEEK_API_KEY = os.environ["DEEPSEEK_API_KEY"]
ICLOUD_USER = os.environ["ICLOUD_USER"]       # your Apple ID email
ICLOUD_PASS = os.environ["ICLOUD_APP_PASS"]   # app-specific password

# DeepSeek client (OpenAI-compatible)
client = OpenAI(api_key=DEEPSEEK_API_KEY, base_url="https://api.deepseek.com")

EXTRACT_PROMPT = """You are an event extractor. Given a message, extract ALL schedulable events.
Respond ONLY with valid JSON (no markdown).

Output format:
{{"events": [
  {{"title": "...", "date": "YYYY-MM-DD", "time": "HH:MM", "duration_min": 60, "location": "..."}},
  {{"title": "...", "date": "YYYY-MM-DD", "time": "HH:MM", "duration_min": 60, "location": "..."}}
]}}

Rules for extraction:
- If time is missing, default to 09:00 AM
- If date is missing, use today's date
- If duration is missing, default to 60 minutes
- If location is missing, leave as empty string
- Parse dates flexibly: "Tues 14 apr" → extract date, "Fri 17 apr" → extract date
- Extract ALL events, even abbreviated ones
- "330pm" = "15:30", "945am" = "09:45"

EXAMPLES:

Input: "Tues 14 apr dinner together, meet up"
Output: {{"events": [{{"title": "dinner together, meet up", "date": "2026-04-14", "time": "19:00", "duration_min": 120, "location": "home"}}]}}

Input: "Fri 17 apr
- morning fasted gym
- lunch at dim sum place
- 330pm 1.5h wellness"
Output: {{"events": [
  {{"title": "morning fasted gym", "date": "2026-04-17", "time": "07:00", "duration_min": 60, "location": "thegym"}},
  {{"title": "lunch at dim sum place", "date": "2026-04-17", "time": "12:00", "duration_min": 60, "location": "dimsumplace"}},
  {{"title": "wellness", "date": "2026-04-17", "time": "15:30", "duration_min": 90, "location": "wellness"}}
]}}

NOTE: Non-event text like "u decide where" or (Context notes) should NOT be extracted as separate events.

Today is {today}. Infer the year if not stated. For dates like "Tues 14 apr", infer the year as {year}."""


def get_calendar():
    client = caldav.DAVClient(
        url="https://caldav.icloud.com/",
        username=ICLOUD_USER,
        password=ICLOUD_PASS
    )
    principal = client.principal()
    calendars = principal.calendars()

    # Return the one named 'Home' or 'Calendar', or just the first
    for cal in calendars:
        if cal.get_display_name() in ("Agentic"):
            return cal, cal.url
    return None, None


def create_event(details: dict):

    start = datetime.strptime(
        f"{details['date']} {details['time']}", "%Y-%m-%d %H:%M")
    end = start + timedelta(minutes=details.get("duration_min", 60))

    # iCloud requires a UID and DTSTAMP
    event_uid = str(uuid.uuid4())
    now = datetime.now(UTC).strftime("%Y%m%dT%H%M%SZ")
    cal, url = get_calendar()
    if not cal:
        print("❌ Could not find calendar")
        return

    ical = f"""BEGIN:VCALENDAR
VERSION:2.0
PRODID:-//TelegramBot//EN
BEGIN:VEVENT
UID:{event_uid}
DTSTAMP:{now}
SUMMARY:{details['title']}
DTSTART:{start.strftime('%Y%m%dT%H%M%S')}
DTEND:{end.strftime('%Y%m%dT%H%M%S')}
LOCATION:{details.get('location', '')}
END:VEVENT
END:VCALENDAR"""
    cal.add_event(ical)  # This will save the event to iCloud


def search_and_delete_event(keyword: str) -> str:
    event_to_delete = search_event(keyword)
    print(event_to_delete)  # Debug: print the event object
    if event_to_delete is None:
        return f"No event found containing '{keyword}'."
    try:
        event_to_delete.delete()
        return f"Deleted event: {event_to_delete.icalendar_component.get('summary')}"
    except Exception as e:
        return f"Error deleting event: {str(e)}"


def search_event(keyword: str, dstart=None, dend=None):
    """Search for events containing keyword. Returns a caldav event object."""
    cal, url = get_calendar()
    if cal is None:
        print("❌ Could not find calendar")
        return None

    # Use datetime objects, not strings
    if dstart is None:
        dstart = datetime.now(UTC)
    if dend is None:
        # Search for events in the next 30 days
        dend = datetime.now(UTC) + timedelta(days=30)

    try:
        # Get all events from calendar
        events_fetched = cal.search(event=True, expand=False)

        for event in events_fetched:
            summary = event.icalendar_component.get("summary")
            if summary and keyword.lower() in summary.lower():
                print(f"Found event: {summary}")
                return event
    except Exception as e:
        print(f"❌ Error searching events: {str(e)}")
        return None

    return None


async def add_cmd(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Parse and add multiple events from user input"""
    # Check if there's text after /add or if it's a reply to another message
    text = None

    if context.args:
        # /add event description here
        text = " ".join(context.args)
    elif update.message.reply_to_message:
        # /add as reply to another message
        text = update.message.reply_to_message.text
    else:
        await update.message.reply_text("Usage: /add <events>\nExample:\n/add Tues 14 apr\ndinner 7pm")
        return

    if not text:
        await update.message.reply_text("No text to process")
        return

    today = datetime.now().strftime("%Y-%m-%d")
    year = datetime.now().year

    response = client.chat.completions.create(
        model="deepseek-chat",
        max_tokens=8192,
        messages=[{"role": "user", "content": EXTRACT_PROMPT.format(
            today=today, year=year) + f"\n\nMessage: {text}"}],
        stream=False
    )

    raw = response.choices[0].message.content.strip()
    try:
        data = json.loads(raw)
    except json.JSONDecodeError as e:
        truncated = (raw[:300] + "...") if len(raw) > 300 else raw
        await update.message.reply_text(f"❌ Failed to parse response:\n```\n{truncated}\n```\nError: {str(e)}")
        return

    events = data.get("events", [])

    if not events:
        await update.message.reply_text("❌ No events found to add")
        return

    success_count = 0
    for event in events:
        try:
            create_event(event)
            success_count += 1
        except Exception as e:
            await update.message.reply_text(f"⚠️ Error adding '{event.get('title')}': {str(e)}")

    result = f"✅ Added {success_count}/{len(events)} events:\n"
    for i, event in enumerate(events, 1):
        result += f"\n{i}. {event['title']}\n   {event['date']} at {event['time']}"

    await update.message.reply_text(result)


async def delete_cmd(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not context.args:
        await update.message.reply_text("Usage: /delete <keyword>\nExample: /delete Property Viewing")
        return

    keyword = " ".join(context.args)
    await update.message.reply_text(f"Searching for '{keyword}'...")

    result = search_and_delete_event(keyword)
    await update.message.reply_text(result)

# Register it alongside your existing handler


class Health(BaseHTTPRequestHandler):
    def do_GET(self):
        self.send_response(200)
        self.end_headers()
        self.wfile.write(b"ok")

    def log_message(self, *args):
        pass  # silence access logs


def run_health():
    HTTPServer(("0.0.0.0", 8080), Health).serve_forever()


if __name__ == "__main__":

    threading.Thread(target=run_health, daemon=True).start()

    app = ApplicationBuilder().token(TELEGRAM_TOKEN).build()
    app.add_handler(CommandHandler("add", add_cmd))
    app.add_handler(CommandHandler("delete", delete_cmd))
    print("Bot is running...")
    app.run_polling(drop_pending_updates=True)

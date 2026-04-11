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

EXTRACT_PROMPT = """You are an event extractor. Given a message, decide if it contains a schedulable event.
If yes, respond ONLY with valid JSON (no markdown):
{{"event": true, "title": "...", "date": "YYYY-MM-DD", "time": "HH:MM", "duration_min": 60, "location": "..."}}
If event details are missing, infer them if possible. 
For example, if the message says "Meeting tomorrow at 3pm", and today is 2024-06-01, you can infer the date as "2024-06-02".
If no duration is mentioned, default to 60 minutes. 
If no location is mentioned, leave it as Singapore default.
If no event is found, respond ONLY with: {{"event": false}}
Today is {today}. Infer the year if not stated."""


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


async def handle_message(update: Update, context: ContextTypes.DEFAULT_TYPE):
    text = update.message.text
    if not text:
        return

    today = datetime.now().strftime("%Y-%m-%d")
    response = client.chat.completions.create(
        model="deepseek-chat",
        max_tokens=300,
        messages=[{"role": "user", "content": EXTRACT_PROMPT.format(
            today=today) + f"\n\nMessage: {text}"}],
        stream=False
    )

    raw = response.choices[0].message.content.strip()
    data = json.loads(raw)

    if data.get("event"):
        create_event(data)
        await update.message.reply_text(
            f"📅 Added to iOS Calendar:\n{data['title']}\n{data['date']} at {data['time']}"
        )


async def delete_cmd(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not context.args:
        await update.message.reply_text("Usage: /delete <keyword>\nExample: /delete Property Viewing")
        return

    keyword = " ".join(context.args)
    await update.message.reply_text(f"Searching for '{keyword}'...")

    result = search_and_delete_event(keyword)
    await update.message.reply_text(result)

# Register it alongside your existing handler


app = ApplicationBuilder().token(TELEGRAM_TOKEN).build()
app.add_handler(MessageHandler(
    filters.TEXT & ~filters.COMMAND, handle_message))
app.add_handler(CommandHandler("delete", delete_cmd))
app.run_polling()

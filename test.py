
import os
import re
from telegram import Update
from telegram.ext import ApplicationBuilder, MessageHandler, filters, ContextTypes
from openai import OpenAI
import caldav
from datetime import datetime
import json
from dotenv import load_dotenv
from datetime import datetime, timedelta
from caldav.elements import dav
import uuid


load_dotenv()  # reads variables from a .env file and sets them in os.environ

ICLOUD_USER = os.environ["ICLOUD_USER"]
ICLOUD_PASS = os.environ["ICLOUD_APP_PASS"]


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
    """Create an event in iCloud Calendar"""
    start = datetime.strptime(
        f"{details['date']} {details['time']}", "%Y-%m-%d %H:%M")
    end = start + timedelta(minutes=details.get("duration_min", 60))

    # iCloud requires a UID and DTSTAMP
    event_uid = str(uuid.uuid4())
    now = datetime.utcnow().strftime("%Y%m%dT%H%M%SZ")

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

    try:
        cal.add_event(ical)
        print(f"✅ Event created: {details['title']}")
    except Exception as e:
        print(f"❌ Error creating event: {e}")


# Test create_event
test_event = {
    "title": "Test Meeting",
    "date": "2026-04-15",
    "time": "14:30",
    "duration_min": 90,
    "location": "Test Location"
}

print("Testing create_event with:")
print(f"  Title: {test_event['title']}")
print(f"  Date: {test_event['date']}")
print(f"  Time: {test_event['time']}")
print(f"  Duration: {test_event['duration_min']} minutes")
print(f"  Location: {test_event['location']}")
print()

create_event(test_event)

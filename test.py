
from telegram.ext import ContextTypes
from telegram import Update, Chat, User, Message
from bot import add_cmd, create_event, EXTRACT_PROMPT
import unittest
from unittest.mock import AsyncMock, MagicMock, patch
import json
from datetime import datetime, timedelta
import sys
import os

# Add parent directory to path to import bot
sys.path.insert(0, os.path.dirname(__file__))


class TestAddCmd(unittest.TestCase):
    """Test the /add command with multiple events"""

    def setUp(self):
        """Set up test fixtures"""
        self.today = datetime(2026, 4, 14)

    def test_extract_prompt_format(self):
        """Test that EXTRACT_PROMPT has correct format placeholders"""
        formatted = EXTRACT_PROMPT.format(today="2026-04-14", year=2026)
        self.assertIn("events", formatted)
        self.assertIn("Tues 14 apr", formatted)
        self.assertIn("EXAMPLES:", formatted)
        self.assertNotIn("{today}", formatted)
        self.assertNotIn("{year}", formatted)

    def test_multiple_events_extraction(self):
        """Test extraction of 9 events from multi-day scenario"""
        multi_event_text = """Tues 14 apr
dinner tgt, clar stayover
--- u decide where to eat

Fri 17 apr
- morning fasted gym
- lunch @ chalao
- 330pm 1.5h yupinzudao massage 

Sat 18 apr
-11am gardenvista
- 2pm dainstree

Sun 19 apr
- 945-1030am clar spin orchard. rch FH at 1110am
- 1130am capri
- 4pm suites de laurel"""

        # Mock LLM response with 9 events
        mock_response = {
            "events": [
                {"title": "dinner tgt, clar stayover", "date": "2026-04-14",
                    "time": "19:00", "duration_min": 120, "location": ""},
                {"title": "morning fasted gym", "date": "2026-04-17",
                    "time": "07:00", "duration_min": 60, "location": ""},
                {"title": "lunch @ chalao", "date": "2026-04-17",
                    "time": "12:00", "duration_min": 60, "location": "chalao"},
                {"title": "yupinzudao massage", "date": "2026-04-17",
                    "time": "15:30", "duration_min": 90, "location": "yupinzudao"},
                {"title": "gardenvista", "date": "2026-04-18", "time": "11:00",
                    "duration_min": 60, "location": "gardenvista"},
                {"title": "dainstree", "date": "2026-04-18", "time": "14:00",
                    "duration_min": 60, "location": "dainstree"},
                {"title": "clar spin orchard. rch FH", "date": "2026-04-19",
                    "time": "09:45", "duration_min": 45, "location": "orchard"},
                {"title": "capri", "date": "2026-04-19", "time": "11:30",
                    "duration_min": 60, "location": "capri"},
                {"title": "suites de laurel", "date": "2026-04-19", "time": "16:00",
                    "duration_min": 60, "location": "suites de laurel"}
            ]
        }

        # Verify we have 9 events
        self.assertEqual(len(mock_response["events"]), 9)

        # Verify event structure
        for event in mock_response["events"]:
            self.assertIn("title", event)
            self.assertIn("date", event)
            self.assertIn("time", event)
            self.assertIn("duration_min", event)
            self.assertIn("location", event)


class TestAddCmdAsync(unittest.IsolatedAsyncioTestCase):
    """Async tests for the /add command"""

    @patch('bot.client')
    @patch('bot.create_event')
    async def test_add_cmd_with_args(self, mock_create_event, mock_client):
        """Test /add command with event text as arguments"""
        # Mock the LLM response
        mock_response = MagicMock()
        mock_response.choices[0].message.content = json.dumps({
            "events": [
                {"title": "Test Event 1", "date": "2026-04-15",
                    "time": "14:00", "duration_min": 60, "location": "Test"},
                {"title": "Test Event 2", "date": "2026-04-16",
                    "time": "10:00", "duration_min": 90, "location": ""}
            ]
        })
        mock_client.chat.completions.create.return_value = mock_response

        # Create mock update and context
        update = AsyncMock(spec=Update)
        update.message.reply_text = AsyncMock()

        context = AsyncMock(spec=ContextTypes.DEFAULT_TYPE)
        context.args = ["test", "event", "here"]

        # Call add_cmd
        await add_cmd(update, context)

        # Verify create_event was called twice
        self.assertEqual(mock_create_event.call_count, 2)

        # Verify reply was sent
        update.message.reply_text.assert_called_once()
        reply_text = update.message.reply_text.call_args[0][0]
        self.assertIn("✅ Added 2/2 events", reply_text)
        self.assertIn("Test Event 1", reply_text)
        self.assertIn("Test Event 2", reply_text)

    @patch('bot.client')
    async def test_add_cmd_no_text(self, mock_client):
        """Test /add command with no text"""
        update = AsyncMock(spec=Update)
        update.message.reply_text = AsyncMock()

        context = AsyncMock(spec=ContextTypes.DEFAULT_TYPE)
        context.args = []
        update.message.reply_to_message = None

        # Call add_cmd
        await add_cmd(update, context)

        # Verify usage message was sent
        update.message.reply_text.assert_called_once()
        reply_text = update.message.reply_text.call_args[0][0]
        self.assertIn("Usage: /add", reply_text)

    @patch('bot.client')
    async def test_add_cmd_no_events_extracted(self, mock_client):
        """Test /add command when no events are extracted"""
        mock_response = MagicMock()
        mock_response.choices[0].message.content = json.dumps({"events": []})
        mock_client.chat.completions.create.return_value = mock_response

        update = AsyncMock(spec=Update)
        update.message.reply_text = AsyncMock()

        context = AsyncMock(spec=ContextTypes.DEFAULT_TYPE)
        context.args = ["random", "text"]

        await add_cmd(update, context)

        update.message.reply_text.assert_called_once()
        reply_text = update.message.reply_text.call_args[0][0]
        self.assertIn("❌ No events found", reply_text)

    def test_create_event_details(self):
        """Test create_event with mock calendar"""
        test_event = {
            "title": "Test Meeting",
            "date": "2026-04-15",
            "time": "14:30",
            "duration_min": 90,
            "location": "Test Location"
        }

        with patch('bot.get_calendar') as mock_get_cal:
            mock_cal = MagicMock()
            mock_get_cal.return_value = (mock_cal, "http://test")

            create_event(test_event)

            # Verify calendar.add_event was called
            mock_cal.add_event.assert_called_once()

            # Verify the iCal format
            ical_content = mock_cal.add_event.call_args[0][0]
            self.assertIn("Test Meeting", ical_content)
            self.assertIn("20260415", ical_content)  # YYYYMMDD format
            self.assertIn("143000", ical_content)  # HH:MM:SS format


if __name__ == "__main__":
    unittest.main()

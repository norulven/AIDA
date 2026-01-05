"""Calendar (CalDAV) client operations for Aida."""

import caldav
import logging
from datetime import datetime, timedelta
from typing import List, Dict, Optional

from src.core.config import MailConfig as CalendarConfig  # Using MailConfig for creds

# Configure logging
logger = logging.getLogger("aida.calendar")
logger.setLevel(logging.DEBUG)
if not logger.handlers:
    fh = logging.FileHandler('/tmp/aida_calendar.log')
    fh.setFormatter(logging.Formatter('%(asctime)s - %(levelname)s - %(message)s'))
    logger.addHandler(fh)

class CalendarClient:
    """Handles CalDAV connections."""

    def __init__(self, config: CalendarConfig):
        self.config = config
        self.client: Optional[caldav.DAVClient] = None
        logger.info("CalendarClient initialized.")

    def _ensure_connected(self) -> bool:
        """Ensures connection to CalDAV server."""
        if not self.config.calendar_enabled:
            logger.warning("Calendar integration is not enabled.")
            return False
        if not self.config.caldav_url or not self.config.email or not self.config.password:
            logger.error("CalDAV URL or credentials not set.")
            return False
            
        if self.client:
            return True

        try:
            logger.info(f"Connecting to CalDAV URL: {self.config.caldav_url}")
            self.client = caldav.DAVClient(
                url=self.config.caldav_url,
                username=self.config.email,
                password=self.config.password,
            )
            return True
        except Exception as e:
            logger.error(f"Failed to connect to CalDAV server: {e}", exc_info=True)
            self.client = None
            return False

    def get_todays_events(self) -> List[Dict]:
        """Fetches and returns today's calendar events."""
        events_summary = []
        if not self._ensure_connected():
            return []

        try:
            my_principal = self.client.principal()
            calendars = my_principal.calendars()
            
            if not calendars:
                logger.warning("No calendars found.")
                return []

            # Assume we use the first calendar
            calendar = calendars[0]
            logger.info(f"Using calendar: {calendar.name}")
            
            today_start = datetime.now().replace(hour=0, minute=0, second=0)
            today_end = today_start + timedelta(days=1)

            events = calendar.date_search(start=today_start, end=today_end)
            
            for event in events:
                vevent = event.vobject_instance.vevent
                summary = vevent.summary.value
                start_time = ""
                
                # Check if it's a datetime or date object
                if hasattr(vevent.dtstart.value, 'hour'):
                    start_time = vevent.dtstart.value.strftime("%-I:%M %p")
                
                events_summary.append({
                    "summary": summary,
                    "start_time": start_time,
                })
            
            logger.info(f"Fetched {len(events_summary)} events for today.")
            return events_summary

        except Exception as e:
            logger.error(f"Error fetching calendar events: {e}", exc_info=True)
            return []

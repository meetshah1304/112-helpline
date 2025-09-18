# modules/festivals_ics.py
import requests
import pandas as pd
from icalendar import Calendar

# Google public Indian holiday/calendar ICS feed
ICS_URL = "https://calendar.google.com/calendar/ical/en.indian%23holiday%40group.v.calendar.google.com/public/basic.ics"

def fetch_festivals_from_ics(url: str = ICS_URL):
    """
    Fetch events from an ICS feed and return a list of tuples:
    [(name, pd.Timestamp(start), pd.Timestamp(end)), ...]
    NOTE: Google ICS typically sets DTEND as exclusive; we convert to inclusive end.
    """
    resp = requests.get(url, timeout=15)
    resp.raise_for_status()

    cal = Calendar.from_ical(resp.content)
    festivals = []
    for component in cal.walk():
        if component.name == "VEVENT":
            name = str(component.get("SUMMARY"))
            dtstart = component.get("DTSTART").dt
            dtend = component.get("DTEND").dt

            # Normalize to pandas Timestamp
            start = pd.to_datetime(dtstart)
            end = pd.to_datetime(dtend)

            # For all-day events ICS often uses date-only and dtend is exclusive (next day).
            # Make end inclusive (subtract 1 day) for date-only events and when dtend > start.
            if hasattr(dtstart, "strftime") and dtstart.__class__.__name__ == "date" and not hasattr(dtstart, "hour"):
                # date-only event
                end = end - pd.Timedelta(days=1)

            # If end < start (rare), set end = start
            if end < start:
                end = start

            festivals.append((name, start, end))
    return festivals

import json
import logging
import uuid
from datetime import datetime, date
from typing import Any, Dict, List, Optional
import dateutil.parser

from jarvis.config import CALENDAR_FILE
from jarvis.tools.registry import register_tool

logger = logging.getLogger(__name__)

def _load_events() -> List[Dict[str, Any]]:
    if not CALENDAR_FILE.exists():
        return []
    try:
        with open(CALENDAR_FILE, "r", encoding="utf-8") as f:
            return json.load(f)
    except Exception as e:
        logger.error(f"Error reading calendar file: {e}")
        return []


def _save_events(events: List[Dict[str, Any]]):
    try:
        with open(CALENDAR_FILE, "w", encoding="utf-8") as f:
            json.dump(events, f, indent=2, default=str)
    except Exception as e:
        logger.error(f"Error saving calendar file: {e}")


@register_tool(
    name="create_calendar_event",
    description="Schedule an event, meeting, or appointment on the user's calendar.",
    parameters={
        "title": {"type": "string", "description": "Title or subject of the event", "required": True},
        "date_str": {"type": "string", "description": "Date of the event (e.g. 'tomorrow', '2026-09-30', 'next Friday')", "required": True},
        "time_str": {"type": "string", "description": "Start time (e.g. '10:00 AM', '14:30', '3 PM')", "required": True},
        "duration_minutes": {"type": "int", "description": "Duration in minutes (default 60)", "required": False},
        "description": {"type": "string", "description": "Optional notes or location details", "required": False}
    }
)
def create_calendar_event(
    title: str,
    date_str: str,
    time_str: str,
    duration_minutes: int = 60,
    description: str = ""
) -> Dict[str, Any]:
    """Add a calendar event."""
    from jarvis.tools.reminders import parse_natural_time

    # Combine date and time for robust parsing
    combined = f"{date_str} {time_str}".strip()
    dt = parse_natural_time(combined)
    if not dt:
        try:
            dt = dateutil.parser.parse(combined, fuzzy=True)
        except Exception:
            dt = datetime.now().replace(minute=0, second=0) + datetime.timedelta(hours=1)

    events = _load_events()
    event_id = str(uuid.uuid4())[:8]

    event = {
        "id": event_id,
        "title": title,
        "date": dt.date().isoformat(),
        "time": dt.strftime("%I:%M %p"),
        "datetime_iso": dt.isoformat(),
        "duration_minutes": duration_minutes or 60,
        "description": description or "",
        "created_at": datetime.now().isoformat()
    }
    events.append(event)
    _save_events(events)

    return {
        "success": True,
        "id": event_id,
        "title": title,
        "scheduled_for": f"{dt.strftime('%A, %B %d, %Y at %I:%M %p')}",
        "message": f"Calendar event '{title}' scheduled for {dt.strftime('%A, %B %d at %I:%M %p')}."
    }


@register_tool(
    name="list_calendar_events",
    description="Retrieve calendar events. Optionally filter by date (e.g., 'today', 'tomorrow', '2026-09-30').",
    parameters={
        "filter_date": {"type": "string", "description": "Optional date filter or empty for all upcoming events", "required": False}
    }
)
def list_calendar_events(filter_date: str = "") -> Dict[str, Any]:
    """List calendar events."""
    events = _load_events()
    if not events:
        return {"success": True, "count": 0, "events": [], "message": "No events found on your calendar."}

    if filter_date:
        filter_lower = filter_date.lower().strip()
        from jarvis.tools.reminders import parse_natural_time
        target_dt = parse_natural_time(filter_lower)
        if target_dt:
            target_iso = target_dt.date().isoformat()
            matched = [e for e in events if e.get("date") == target_iso]
        else:
            matched = [e for e in events if filter_lower in e.get("date", "").lower() or filter_lower in e.get("title", "").lower()]
    else:
        matched = events

    # Sort chronologically
    sorted_events = sorted(matched, key=lambda x: x.get("datetime_iso", ""))
    return {
        "success": True,
        "count": len(sorted_events),
        "events": sorted_events
    }


@register_tool(
    name="delete_calendar_event",
    description="Cancel or delete a scheduled event from the calendar.",
    parameters={
        "event_id": {"type": "string", "description": "The unique ID of the event to delete", "required": True}
    },
    requires_confirmation=True,
    dangerous=False
)
def delete_calendar_event(event_id: str) -> Dict[str, Any]:
    """Remove a calendar event."""
    events = _load_events()
    initial_len = len(events)
    events = [e for e in events if e.get("id") != event_id]
    if len(events) == initial_len:
        return {"success": False, "error": f"Event '{event_id}' not found."}

    _save_events(events)
    return {"success": True, "message": f"Event {event_id} has been cancelled."}
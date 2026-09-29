import json
import logging
import re
import threading
import time
import uuid
from datetime import datetime, timedelta
from typing import Any, Callable, Dict, List, Optional
import dateutil.parser

from jarvis.config import REMINDERS_FILE
from jarvis.tools.registry import register_tool

logger = logging.getLogger(__name__)

# Callbacks for reminder triggers (e.g. speech, websocket broadcast)
_reminder_listeners: List[Callable[[Dict[str, Any]], None]] = []


def register_reminder_listener(callback: Callable[[Dict[str, Any]], None]):
    """Register listener callback when reminder triggers."""
    if callback not in _reminder_listeners:
        _reminder_listeners.append(callback)


def _load_reminders() -> List[Dict[str, Any]]:
    if not REMINDERS_FILE.exists():
        return []
    try:
        with open(REMINDERS_FILE, "r", encoding="utf-8") as f:
            return json.load(f)
    except Exception as e:
        logger.error(f"Error reading reminders file: {e}")
        return []


def _save_reminders(reminders: List[Dict[str, Any]]):
    try:
        with open(REMINDERS_FILE, "w", encoding="utf-8") as f:
            json.dump(reminders, f, indent=2, default=str)
    except Exception as e:
        logger.error(f"Error saving reminders file: {e}")


def parse_natural_time(time_str: str) -> Optional[datetime]:
    """Parse natural language relative or absolute time strings."""
    now = datetime.now()
    clean = time_str.lower().strip()

    # Relative: "in X minutes / hours / seconds / days"
    rel_match = re.search(r"in\s+(\d+)\s*(minute|min|hour|hr|second|sec|day)s?", clean)
    if rel_match:
        qty = int(rel_match.group(1))
        unit = rel_match.group(2)
        if unit.startswith("min"):
            return now + timedelta(minutes=qty)
        elif unit.startswith("hour") or unit.startswith("hr"):
            return now + timedelta(hours=qty)
        elif unit.startswith("sec"):
            return now + timedelta(seconds=qty)
        elif unit.startswith("day"):
            return now + timedelta(days=qty)

    # "tomorrow at HH:MM AM/PM" or "tomorrow at HH AM/PM"
    if "tomorrow" in clean:
        target_date = (now + timedelta(days=1)).date()
        time_part = re.sub(r".*tomorrow\s*(at\s*)?", "", clean).strip()
        if time_part:
            try:
                parsed_time = dateutil.parser.parse(time_part).time()
                return datetime.combine(target_date, parsed_time)
            except Exception:
                # Default 08:00 AM if no valid time parsed
                return datetime.combine(target_date, datetime.min.time().replace(hour=8))
        else:
            return datetime.combine(target_date, datetime.min.time().replace(hour=8))

    # "today at HH:MM AM/PM"
    if "today" in clean:
        target_date = now.date()
        time_part = re.sub(r".*today\s*(at\s*)?", "", clean).strip()
        if time_part:
            try:
                parsed_time = dateutil.parser.parse(time_part).time()
                return datetime.combine(target_date, parsed_time)
            except Exception:
                pass

    # Generic dateutil parse
    try:
        parsed = dateutil.parser.parse(time_str, fuzzy=True, default=now)
        # If parsed time is earlier than now on the same day, user likely meant next occurrence or tomorrow
        if parsed <= now and (parsed - now).total_seconds() < 0 and "yesterday" not in clean:
            # If only time was specified, advance by 1 day
            parsed += timedelta(days=1)
        return parsed
    except Exception:
        return None


@register_tool(
    name="create_reminder",
    description="Set a time-based reminder for the user. Example: 'tomorrow at 8 AM', 'in 30 minutes'.",
    parameters={
        "title": {"type": "string", "description": "What to remind the user about (e.g., 'submit project', 'call John')", "required": True},
        "due_time": {"type": "string", "description": "When to trigger the reminder (e.g. 'tomorrow at 8 AM', 'in 15 minutes', '2026-09-30 08:00')", "required": True},
        "note": {"type": "string", "description": "Optional additional notes or context", "required": False}
    }
)
def create_reminder(title: str, due_time: str, note: str = "") -> Dict[str, Any]:
    """Create and persist a new reminder."""
    dt = parse_natural_time(due_time)
    if not dt:
        return {"success": False, "error": f"Could not understand time '{due_time}'. Please provide a valid time or relative duration."}

    reminders = _load_reminders()
    reminder_id = str(uuid.uuid4())[:8]

    # Human readable due string
    human_due = dt.strftime("%A, %b %d at %I:%M %p")

    new_item = {
        "id": reminder_id,
        "title": title,
        "due_timestamp": dt.isoformat(),
        "due_human": human_due,
        "note": note,
        "created_at": datetime.now().isoformat(),
        "completed": False,
        "triggered": False
    }
    reminders.append(new_item)
    _save_reminders(reminders)

    return {
        "success": True,
        "id": reminder_id,
        "title": title,
        "due_at": human_due,
        "iso_due": dt.isoformat(),
        "confirmation": f"Done. I've set a reminder for {title} on {human_due}."
    }


@register_tool(
    name="list_reminders",
    description="List active or all reminders for the user.",
    parameters={
        "include_completed": {"type": "bool", "description": "Whether to include completed or past triggered reminders", "required": False}
    }
)
def list_reminders(include_completed: bool = False) -> Dict[str, Any]:
    """List pending reminders."""
    reminders = _load_reminders()
    if not include_completed:
        active = [r for r in reminders if not r.get("completed", False)]
    else:
        active = reminders

    return {
        "success": True,
        "count": len(active),
        "reminders": sorted(active, key=lambda x: x.get("due_timestamp", ""))
    }


@register_tool(
    name="delete_reminder",
    description="Delete a reminder by ID.",
    parameters={
        "reminder_id": {"type": "string", "description": "The unique ID of the reminder to delete", "required": True}
    },
    requires_confirmation=True,
    dangerous=False
)
def delete_reminder(reminder_id: str) -> Dict[str, Any]:
    """Delete a reminder."""
    reminders = _load_reminders()
    initial_len = len(reminders)
    reminders = [r for r in reminders if r.get("id") != reminder_id]
    if len(reminders) == initial_len:
        return {"success": False, "error": f"Reminder with ID '{reminder_id}' not found."}

    _save_reminders(reminders)
    return {"success": True, "message": f"Reminder {reminder_id} has been removed."}


# Background Reminder Monitoring Daemon
class ReminderDaemon(threading.Thread):
    def __init__(self, check_interval: float = 3.0):
        super().__init__(daemon=True, name="MineReminderDaemon")
        self.check_interval = check_interval
        self.running = True

    def run(self):
        logger.info("Reminder Daemon started.")
        while self.running:
            try:
                now = datetime.now()
                reminders = _load_reminders()
                changed = False

                for r in reminders:
                    if not r.get("completed") and not r.get("triggered"):
                        due_dt = datetime.fromisoformat(r["due_timestamp"])
                        if now >= due_dt:
                            r["triggered"] = True
                            r["completed"] = True
                            changed = True
                            logger.info(f"Reminder Triggered: {r['title']}")
                            # Notify listeners
                            for listener in _reminder_listeners:
                                try:
                                    listener(r)
                                except Exception as ex:
                                    logger.error(f"Error in reminder listener: {ex}")

                if changed:
                    _save_reminders(reminders)
            except Exception as e:
                logger.error(f"Error in reminder daemon tick: {e}")

            time.sleep(self.check_interval)

    def stop(self):
        self.running = False


# Start daemon singleton
_daemon = ReminderDaemon()
_daemon.start()
# Import all tools to ensure registration
from jarvis.tools.registry import registry, register_tool
import jarvis.tools.search
import jarvis.tools.files
import jarvis.tools.reminders
import jarvis.tools.calendar
import jarvis.tools.system
import jarvis.tools.entertainment
import jarvis.core.memory

__all__ = ["registry", "register_tool"]
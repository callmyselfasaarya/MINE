import logging
from typing import Any, Dict, List
from jarvis.config import SYSTEM_PROMPT
from jarvis.core.memory import get_memory_context_prompt

logger = logging.getLogger(__name__)

class ConversationManager:
    def __init__(self, max_history_turns: int = 15):
        self.max_history_turns = max_history_turns
        self.history: List[Dict[str, Any]] = []

    def get_system_instruction(self) -> str:
        """Compose system instruction including current date/time and remembered facts."""
        from datetime import datetime
        now_str = datetime.now().strftime("%A, %B %d, %Y %I:%M %p")
        time_context = f"\nCurrent Date and Time: {now_str}."
        memory_context = get_memory_context_prompt()
        return SYSTEM_PROMPT.strip() + "\n" + time_context + "\n" + memory_context

    def add_user_message(self, content: str):
        self.history.append({
            "role": "user",
            "content": content
        })
        self._trim()

    def add_assistant_message(self, content: str):
        self.history.append({
            "role": "model",
            "content": content
        })
        self._trim()

    def add_tool_interaction(self, tool_name: str, args: Dict[str, Any], result: Any):
        self.history.append({
            "role": "tool",
            "tool_name": tool_name,
            "args": args,
            "result": result
        })
        self._trim()

    def _trim(self):
        # Keep recent turns to prevent context bloat
        if len(self.history) > self.max_history_turns * 2:
            self.history = self.history[-(self.max_history_turns * 2):]

    def clear(self):
        self.history = []

    def get_messages(self) -> List[Dict[str, Any]]:
        return list(self.history)
import logging
from datetime import datetime
from typing import Any, Dict, List, Optional
from jarvis.config import SYSTEM_PROMPT
from jarvis.memory import memory

logger = logging.getLogger(__name__)

class ConversationManager:
    """
    Dialogue and context manager:
    - Maintains multi-turn conversation buffer
    - Injects system prompt with live timestamp, long-term memory, working memory, and semantic context
    """

    def __init__(self, max_history_turns: int = 15):
        self.max_history_turns = max_history_turns
        self.history: List[Dict[str, Any]] = []

    def get_system_instruction(self, current_query: Optional[str] = None) -> str:
        """Compose system instruction including current date/time, working memory, and memories."""
        now_str = datetime.now().strftime("%A, %B %d, %Y %I:%M %p")
        time_context = f"\nCurrent Date and Time: {now_str}."
        memory_context = memory.get_full_context_prompt(current_query=current_query)
        return SYSTEM_PROMPT.strip() + "\n" + time_context + "\n" + memory_context

    def add_user_message(self, content: str):
        self.history.append({
            "role": "user",
            "content": content
        })
        memory.short_term.add_user_turn(content)
        self._trim()

    def add_assistant_message(self, content: str):
        self.history.append({
            "role": "model",
            "content": content
        })
        memory.short_term.add_assistant_turn(content)
        self._trim()

    def add_tool_interaction(self, tool_name: str, args: Dict[str, Any], result: Any):
        self.history.append({
            "role": "tool",
            "tool_name": tool_name,
            "args": args,
            "result": result
        })
        memory.short_term.add_tool_turn(tool_name, args, result)
        self._trim()

    def _trim(self):
        # Keep recent turns to prevent context bloat
        if len(self.history) > self.max_history_turns * 2:
            self.history = self.history[-(self.max_history_turns * 2):]

    def clear(self):
        self.history = []
        memory.short_term.clear()

    def get_messages(self) -> List[Dict[str, Any]]:
        return list(self.history)
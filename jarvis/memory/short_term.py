import logging
from typing import Any, Dict, List, Optional
from datetime import datetime

logger = logging.getLogger(__name__)

class ShortTermMemory:
    """
    Manages short-term context:
    1. Multi-turn conversation sliding window
    2. Working memory (current task, scratchpad variables, active entities)
    """

    def __init__(self, max_history_turns: int = 15):
        self.max_history_turns = max_history_turns
        self.conversation_history: List[Dict[str, Any]] = []
        self.working_memory: Dict[str, Any] = {
            "current_goal": None,
            "active_topic": None,
            "entities": {},
            "scratchpad": {},
            "last_interaction": None,
        }

    def add_user_turn(self, text: str):
        self.conversation_history.append({
            "role": "user",
            "content": text,
            "timestamp": datetime.now().isoformat()
        })
        self.working_memory["last_interaction"] = datetime.now().isoformat()
        self._trim_history()

    def add_assistant_turn(self, text: str, reasoning: Optional[str] = None):
        turn = {
            "role": "model",
            "content": text,
            "timestamp": datetime.now().isoformat()
        }
        if reasoning:
            turn["reasoning"] = reasoning
        self.conversation_history.append(turn)
        self.working_memory["last_interaction"] = datetime.now().isoformat()
        self._trim_history()

    def add_tool_turn(self, tool_name: str, args: Dict[str, Any], result: Any):
        self.conversation_history.append({
            "role": "tool",
            "tool_name": tool_name,
            "args": args,
            "result": result,
            "timestamp": datetime.now().isoformat()
        })
        self._trim_history()

    def _trim_history(self):
        # Keep last (max_history_turns * 2) entries to avoid overflowing context
        limit = self.max_history_turns * 2
        if len(self.conversation_history) > limit:
            self.conversation_history = self.conversation_history[-limit:]

    def set_goal(self, goal: Optional[str]):
        self.working_memory["current_goal"] = goal

    def get_goal(self) -> Optional[str]:
        return self.working_memory.get("current_goal")

    def set_scratchpad(self, key: str, value: Any):
        self.working_memory["scratchpad"][key] = value

    def get_scratchpad(self, key: str, default: Any = None) -> Any:
        return self.working_memory["scratchpad"].get(key, default)

    def track_entity(self, entity_name: str, entity_value: Any):
        self.working_memory["entities"][entity_name] = {
            "value": entity_value,
            "updated_at": datetime.now().isoformat()
        }

    def get_recent_messages(self, limit: Optional[int] = None) -> List[Dict[str, Any]]:
        if limit:
            return self.conversation_history[-limit:]
        return list(self.conversation_history)

    def get_context_summary(self) -> str:
        """Brief text summary of working memory."""
        items = []
        if self.working_memory.get("current_goal"):
            items.append(f"Active Goal: {self.working_memory['current_goal']}")
        if self.working_memory.get("active_topic"):
            items.append(f"Active Topic: {self.working_memory['active_topic']}")
        if self.working_memory.get("scratchpad"):
            keys = ", ".join(self.working_memory["scratchpad"].keys())
            items.append(f"Scratchpad Keys: {keys}")
        return "\n".join(items) if items else "No active working goals."

    def clear(self):
        self.conversation_history.clear()
        self.working_memory = {
            "current_goal": None,
            "active_topic": None,
            "entities": {},
            "scratchpad": {},
            "last_interaction": None,
        }

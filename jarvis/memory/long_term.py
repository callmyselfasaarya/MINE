import json
import logging
from datetime import datetime
from pathlib import Path
from typing import Any, Dict, List, Optional
from jarvis.config import MEMORY_FILE

logger = logging.getLogger(__name__)

class LongTermMemory:
    """
    Persistent Long-term Memory:
    - User preferences, personal details, habits, important facts
    - Categorized storage in JSON
    - System prompt injection
    """

    def __init__(self, memory_file: Optional[Path] = None):
        self.memory_file = memory_file or MEMORY_FILE

    def _load(self) -> Dict[str, Any]:
        if not self.memory_file.exists():
            return {}
        try:
            with open(self.memory_file, "r", encoding="utf-8") as f:
                return json.load(f)
        except Exception as e:
            logger.error(f"Error loading long term memory: {e}")
            return {}

    def _save(self, data: Dict[str, Any]):
        try:
            self.memory_file.parent.mkdir(parents=True, exist_ok=True)
            with open(self.memory_file, "w", encoding="utf-8") as f:
                json.dump(data, f, indent=2, default=str)
        except Exception as e:
            logger.error(f"Error saving long term memory: {e}")

    def remember(self, topic_or_key: str, information: str, category: str = "general") -> Dict[str, Any]:
        """Store or update a fact in long-term memory."""
        memories = self._load()
        clean_key = topic_or_key.strip().lower().replace(" ", "_")
        memories[clean_key] = {
            "title": topic_or_key.strip(),
            "value": information.strip(),
            "category": (category or "general").strip().lower(),
            "updated_at": datetime.now().isoformat()
        }
        self._save(memories)
        return {
            "success": True,
            "key": clean_key,
            "message": f"Committed to memory under '{topic_or_key}'.",
            "value": information
        }

    def recall(self, query: str = "") -> List[Dict[str, Any]]:
        """Search or list memories."""
        memories = self._load()
        if not query:
            return [
                {
                    "key": k,
                    "topic": v.get("title", k),
                    "value": v.get("value", ""),
                    "category": v.get("category", "general"),
                    "updated_at": v.get("updated_at")
                }
                for k, v in memories.items()
            ]

        q = query.strip().lower()
        results = []
        for k, v in memories.items():
            val = v.get("value", "").lower()
            title = v.get("title", "").lower()
            cat = v.get("category", "").lower()
            if q in k or q in val or q in title or q in cat:
                results.append({
                    "key": k,
                    "topic": v.get("title", k),
                    "value": v.get("value", ""),
                    "category": v.get("category", "general"),
                    "updated_at": v.get("updated_at")
                })
        return results

    def forget(self, topic_or_key: str) -> bool:
        """Remove a fact by key or title."""
        memories = self._load()
        clean_key = topic_or_key.strip().lower().replace(" ", "_")
        if clean_key in memories:
            del memories[clean_key]
            self._save(memories)
            return True

        # Try matching by title
        matched_k = None
        for k, v in memories.items():
            if v.get("title", "").lower() == topic_or_key.strip().lower():
                matched_k = k
                break
        if matched_k:
            del memories[matched_k]
            self._save(memories)
            return True

        return False

    def get_prompt_context(self) -> str:
        """Formatted snippet of remembered items for system prompt."""
        memories = self._load()
        if not memories:
            return ""
        lines = ["\n[Remembered Information & User Context]:"]
        for key, item in memories.items():
            val = item.get("value", "")
            cat = item.get("category", "general")
            lines.append(f"- [{cat.upper()}] {key}: {val}")
        return "\n".join(lines)

    def get_all(self) -> Dict[str, Any]:
        return self._load()

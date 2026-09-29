import json
import logging
from datetime import datetime
from typing import Any, Dict, List, Optional
from jarvis.config import MEMORY_FILE
from jarvis.tools.registry import register_tool

logger = logging.getLogger(__name__)

def _load_memories() -> Dict[str, Any]:
    if not MEMORY_FILE.exists():
        return {}
    try:
        with open(MEMORY_FILE, "r", encoding="utf-8") as f:
            return json.load(f)
    except Exception as e:
        logger.error(f"Error loading memory: {e}")
        return {}


def _save_memories(data: Dict[str, Any]):
    try:
        with open(MEMORY_FILE, "w", encoding="utf-8") as f:
            json.dump(data, f, indent=2, default=str)
    except Exception as e:
        logger.error(f"Error saving memory: {e}")


def get_memory_context_prompt() -> str:
    """Generate a prompt snippet containing remembered facts for the LLM."""
    memories = _load_memories()
    if not memories:
        return ""

    lines = ["\n[Remembered Information & User Context]:"]
    for key, item in memories.items():
        val = item.get("value", "")
        cat = item.get("category", "general")
        lines.append(f"- [{cat.upper()}] {key}: {val}")
    return "\n".join(lines)


@register_tool(
    name="remember_fact",
    description="Save a useful fact, user preference, personal detail, or note to long-term memory. Always use this whenever the user says 'remember that...', 'remember my...', or tells you their preferences or details.",
    parameters={
        "topic_or_key": {"type": "string", "description": "Subject or key (e.g., 'coffee_preference', 'favorite_beverage', 'project_deadline', 'birthday')", "required": True},
        "information": {"type": "string", "description": "The exact fact or information to remember", "required": True},
        "category": {"type": "string", "description": "Category (e.g., 'preference', 'personal', 'work', 'project')", "required": False}
    }
)
def remember_fact(topic_or_key: str, information: str, category: str = "general") -> Dict[str, Any]:
    """Store information into persistent memory."""
    memories = _load_memories()
    clean_key = topic_or_key.strip().lower().replace(" ", "_")

    memories[clean_key] = {
        "title": topic_or_key,
        "value": information,
        "category": category or "general",
        "updated_at": datetime.now().isoformat()
    }
    _save_memories(memories)

    return {
        "success": True,
        "key": clean_key,
        "message": f"I have committed that to memory under '{topic_or_key}'.",
        "value": information
    }


@register_tool(
    name="recall_facts",
    description="Recall remembered facts, user preferences, or saved information from memory.",
    parameters={
        "query": {"type": "string", "description": "Search term or leave empty to list all memories", "required": False}
    }
)
def recall_facts(query: str = "") -> Dict[str, Any]:
    """Search or list remembered items."""
    memories = _load_memories()
    if not memories:
        return {"success": True, "count": 0, "memories": [], "message": "My memory is currently empty, Sir."}

    q = query.lower().strip()
    results = []

    for k, item in memories.items():
        if not q or q in k or q in item.get("value", "").lower() or q in item.get("category", "").lower():
            results.append({
                "key": k,
                "topic": item.get("title", k),
                "value": item.get("value", ""),
                "category": item.get("category", "general"),
                "updated_at": item.get("updated_at")
            })

    return {
        "success": True,
        "count": len(results),
        "results": results
    }


@register_tool(
    name="forget_fact",
    description="Remove a remembered fact from long-term memory.",
    parameters={
        "topic_or_key": {"type": "string", "description": "The key or topic to forget", "required": True}
    },
    requires_confirmation=True,
    dangerous=False
)
def forget_fact(topic_or_key: str) -> Dict[str, Any]:
    """Remove item from memory."""
    memories = _load_memories()
    clean_key = topic_or_key.strip().lower().replace(" ", "_")

    if clean_key in memories:
        del memories[clean_key]
        _save_memories(memories)
        return {"success": True, "message": f"I have forgotten information regarding '{topic_or_key}'."}

    return {"success": False, "error": f"No memory found matching '{topic_or_key}'."}
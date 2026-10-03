import json
import logging
from datetime import datetime
from typing import Any, Dict, List, Optional
from jarvis.config import MEMORY_FILE
from jarvis.tools.registry import register_tool
from jarvis.memory import memory, LongTermMemory, ShortTermMemory, SemanticMemory

logger = logging.getLogger(__name__)

def _load_memories() -> Dict[str, Any]:
    return memory.long_term.get_all()

def _save_memories(data: Dict[str, Any]):
    memory.long_term._save(data)

def get_memory_context_prompt() -> str:
    """Generate a prompt snippet containing remembered facts for the LLM."""
    return memory.long_term.get_prompt_context()

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
    """Store information into persistent long-term memory and index in semantic memory."""
    res = memory.long_term.remember(topic_or_key, information, category)
    # Also index into semantic memory for relevance matching
    memory.semantic.add_entry(
        content=f"{topic_or_key}: {information} ({category})",
        source="fact",
        metadata={"key": res.get("key"), "category": category}
    )
    return {
        "success": True,
        "key": res.get("key"),
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
    """Search or list remembered items from long-term memory."""
    results = memory.long_term.recall(query)
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
    success = memory.long_term.forget(topic_or_key)
    if success:
        return {"success": True, "message": f"I have forgotten information regarding '{topic_or_key}'."}
    return {"success": False, "error": f"No memory found matching '{topic_or_key}'."}

@register_tool(
    name="search_semantic_memory",
    description="Perform semantic search over indexed documents, facts, and conversation snippets.",
    parameters={
        "query": {"type": "string", "description": "Search query or natural language concept to retrieve", "required": True},
        "top_k": {"type": "integer", "description": "Max results to return (default 4)", "required": False}
    }
)
def search_semantic_memory(query: str, top_k: int = 4) -> Dict[str, Any]:
    """Retrieve semantically relevant knowledge."""
    results = memory.semantic.search(query, top_k=top_k)
    return {
        "success": True,
        "count": len(results),
        "results": results
    }
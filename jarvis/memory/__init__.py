import logging
from typing import Any, Dict, List, Optional
from jarvis.memory.short_term import ShortTermMemory
from jarvis.memory.long_term import LongTermMemory
from jarvis.memory.semantic import SemanticMemory

logger = logging.getLogger(__name__)

class MemorySubsystem:
    """
    Unified Memory Subsystem according to Assistant Architecture:
    - Short-term: Conversation buffer & working memory scratchpad
    - Long-term: Persistent user profile, habits, explicit facts
    - Semantic: Document & passage index with similarity search
    """

    def __init__(self):
        self.short_term = ShortTermMemory()
        self.long_term = LongTermMemory()
        self.semantic = SemanticMemory()

    def get_full_context_prompt(self, current_query: Optional[str] = None) -> str:
        """Compose context from long-term memory, working memory, and relevant semantic snippets."""
        sections = []

        # 1. Long term memory
        lt_context = self.long_term.get_prompt_context()
        if lt_context:
            sections.append(lt_context)

        # 2. Short term working context
        wm_context = self.short_term.get_context_summary()
        if wm_context and wm_context != "No active working goals.":
            sections.append(f"\n[Working Context]:\n{wm_context}")

        # 3. Semantic memory search if query is provided
        if current_query:
            matches = self.semantic.search(current_query, top_k=3)
            if matches:
                sem_lines = ["\n[Semantically Relevant Prior Knowledge]:"]
                for m in matches:
                    sem_lines.append(f"- {m['content']} (source: {m.get('source', 'unknown')})")
                sections.append("\n".join(sem_lines))

        return "\n".join(sections)

# Global singleton
memory = MemorySubsystem()

__all__ = ["MemorySubsystem", "ShortTermMemory", "LongTermMemory", "SemanticMemory", "memory"]

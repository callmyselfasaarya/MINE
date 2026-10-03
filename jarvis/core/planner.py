import logging
from typing import Any, Dict, List, Optional
from jarvis.memory import memory

logger = logging.getLogger(__name__)

class PlanningEngine:
    """
    Planning & Decisions Engine for Jarvis Core:
    - Creates and monitors active multi-step plans
    - Coordinates step milestones and tracking
    - Stores plan state in Short-Term Working Memory
    """

    def __init__(self):
        self.active_plan: Optional[Dict[str, Any]] = None

    def create_and_execute_plan(self, goal: str) -> Dict[str, Any]:
        """Delegate goal breakdown and orchestration to PlanningAgent."""
        from jarvis.agents import agents_manager
        logger.info(f"Creating and executing plan for goal: '{goal}'")
        res = agents_manager.dispatch("planning", goal)
        self.active_plan = res
        return res

    def get_active_plan(self) -> Optional[Dict[str, Any]]:
        return self.active_plan

    def cancel_active_plan(self):
        self.active_plan = None
        memory.short_term.set_goal(None)

# Global singleton
planning_engine = PlanningEngine()

__all__ = ["PlanningEngine", "planning_engine"]
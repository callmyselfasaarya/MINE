import logging
from typing import Any, Dict, Optional
from jarvis.agents.base import BaseSubAgent
from jarvis.agents.research import ResearchAgent
from jarvis.agents.coding import CodingAgent
from jarvis.agents.planning import PlanningAgent

logger = logging.getLogger(__name__)

class SubAgentManager:
    """
    Sub-Agents Subsystem according to Assistant Architecture:
    - Research Agent: Multi-source web/document investigations & synthesis
    - Coding Agent: Software development, debugging, and sandbox runner
    - Planning Agent: Complex goal decomposition & multi-step execution
    """

    def __init__(self):
        self.research = ResearchAgent()
        self.coding = CodingAgent()
        self.planning = PlanningAgent()

        self._agents: Dict[str, BaseSubAgent] = {
            "research": self.research,
            "coding": self.coding,
            "planning": self.planning
        }

    def get_agent(self, agent_type: str) -> Optional[BaseSubAgent]:
        return self._agents.get(agent_type.lower())

    def list_agents(self) -> Dict[str, Dict[str, str]]:
        return {
            key: {
                "name": agent.name,
                "role": agent.role,
                "description": agent.description
            }
            for key, agent in self._agents.items()
        }

    def dispatch(self, agent_type: str, task: str, context: Optional[Dict[str, Any]] = None) -> Dict[str, Any]:
        agent = self.get_agent(agent_type)
        if not agent:
            return {
                "success": False,
                "error": f"Agent '{agent_type}' not found. Available agents: {list(self._agents.keys())}"
            }
        return agent.run(task, context=context)

# Global singleton
agents_manager = SubAgentManager()

__all__ = ["SubAgentManager", "ResearchAgent", "CodingAgent", "PlanningAgent", "agents_manager"]

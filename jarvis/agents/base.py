import abc
import logging
from typing import Any, Dict, Optional

logger = logging.getLogger(__name__)

class BaseSubAgent(abc.ABC):
    """
    Abstract Base Class for Specialized Assistant Sub-Agents:
    - Research Agent
    - Coding Agent
    - Planning Agent
    """

    def __init__(self, name: str, role: str, description: str):
        self.name = name
        self.role = role
        self.description = description

    @abc.abstractmethod
    def run(self, task: str, context: Optional[Dict[str, Any]] = None) -> Dict[str, Any]:
        """Execute the delegated task and return a structured outcome."""
        pass

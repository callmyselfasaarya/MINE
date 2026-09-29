"""M.I.N.E. Personal Assistant Package."""
from jarvis import *
from jarvis.core.agent import jarvis_agent as mine_agent, JarvisAgent as MineAgent
from jarvis.config import ASSISTANT_NAME, USER_NAME

__version__ = "1.0.0"
__all__ = ["mine_agent", "MineAgent", "ASSISTANT_NAME", "USER_NAME"]

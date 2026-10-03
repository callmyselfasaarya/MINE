import logging
from jarvis.execution.pc import PCExecutor
from jarvis.execution.browser import BrowserExecutor
from jarvis.execution.smart_home import SmartHomeExecutor
from jarvis.execution.apps_api import AppsAPIExecutor

logger = logging.getLogger(__name__)

class ExecutionLayer:
    """
    Unified Action / Execution Layer according to Assistant Architecture:
    - PC: App launching, keyboard/mouse automation, media controls
    - Browser: URL navigation, browser searches, page text scraping
    - Smart Home: IoT lighting, power switches, climate, scenes
    - Apps & APIs: Weather queries, webhook triggers, external REST integrations
    """

    def __init__(self):
        self.pc = PCExecutor()
        self.browser = BrowserExecutor()
        self.smart_home = SmartHomeExecutor()
        self.apps_api = AppsAPIExecutor()

# Global singleton
execution = ExecutionLayer()

__all__ = ["ExecutionLayer", "PCExecutor", "BrowserExecutor", "SmartHomeExecutor", "AppsAPIExecutor", "execution"]

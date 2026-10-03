import logging
from typing import Any, Dict
from jarvis.tools.registry import register_tool
from jarvis.execution import execution

logger = logging.getLogger(__name__)

@register_tool(
    name="fetch_web_page",
    description="Fetch and extract readable plain text content from a given web URL or article.",
    parameters={
        "url": {"type": "string", "description": "The URL to fetch and read", "required": True},
        "max_chars": {"type": "integer", "description": "Max characters to extract (default 3000)", "required": False}
    }
)
def fetch_web_page(url: str, max_chars: int = 3000) -> Dict[str, Any]:
    """Fetch text from a web page."""
    return execution.browser.fetch_page_text(url, max_chars=max_chars)

@register_tool(
    name="browse_url",
    description="Open a web page or URL in the default desktop browser.",
    parameters={
        "url": {"type": "string", "description": "The URL to open", "required": True}
    }
)
def browse_url(url: str) -> Dict[str, Any]:
    """Open URL in system web browser."""
    return execution.browser.open_url(url)

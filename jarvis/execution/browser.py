import logging
import re
import urllib.parse
import webbrowser
from typing import Any, Dict, Optional
import requests

logger = logging.getLogger(__name__)

class BrowserExecutor:
    """
    Browser Action Execution:
    - Navigating and opening URLs in default web browser
    - Performing web searches directly in browser
    - Scraping and extracting clean readable content from web pages
    """

    def open_url(self, url: str) -> Dict[str, Any]:
        """Open web URL in default system browser."""
        target = url.strip()
        if not target.startswith("http://") and not target.startswith("https://"):
            target = f"https://{target}"
        try:
            webbrowser.open(target)
            return {"success": True, "url": target, "message": f"Opened {target} in browser."}
        except Exception as e:
            logger.error(f"Browser navigation failed: {e}")
            return {"success": False, "error": str(e)}

    def search_in_browser(self, query: str, engine: str = "google") -> Dict[str, Any]:
        """Search query in default browser."""
        q = urllib.parse.quote_plus(query)
        if engine.lower() == "duckduckgo":
            url = f"https://duckduckgo.com/?q={q}"
        else:
            url = f"https://www.google.com/search?q={q}"
        return self.open_url(url)

    def fetch_page_text(self, url: str, max_chars: int = 3500) -> Dict[str, Any]:
        """
        Fetch HTML from URL and extract readable plain text content.
        """
        target = url.strip()
        if not target.startswith("http://") and not target.startswith("https://"):
            target = f"https://{target}"

        headers = {
            "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36"
        }

        try:
            resp = requests.get(target, headers=headers, timeout=10)
            resp.raise_for_status()
            html = resp.text

            # Remove scripts, styles, and tags
            clean = re.sub(r"<(script|style|nav|footer|header)[^>]*>.*?</\1>", " ", html, flags=re.DOTALL | re.IGNORECASE)
            clean = re.sub(r"<[^>]+>", " ", clean)
            clean = re.sub(r"\s+", " ", clean).strip()

            snippet = clean[:max_chars]
            return {
                "success": True,
                "url": target,
                "content": snippet,
                "length": len(snippet),
                "is_truncated": len(clean) > max_chars
            }
        except Exception as e:
            logger.error(f"Failed to fetch {target}: {e}")
            return {"success": False, "error": str(e)}

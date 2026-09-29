import logging
import warnings
from typing import Any, Dict, List
import wikipedia

with warnings.catch_warnings():
    warnings.simplefilter("ignore")
    try:
        from ddgs import DDGS
    except ImportError:
        from duckduckgo_search import DDGS

from jarvis.tools.registry import register_tool

logger = logging.getLogger(__name__)

@register_tool(
    name="search_web",
    description="Search the live internet for recent information, facts, news, and queries using DuckDuckGo.",
    parameters={
        "query": {"type": "string", "description": "The search query string", "required": True},
        "max_results": {"type": "int", "description": "Maximum number of search results to return (default 4)", "required": False}
    }
)
def search_web(query: str, max_results: int = 4) -> List[Dict[str, str]]:
    """Search DuckDuckGo and return concise titles, snippets, and links."""
    try:
        results = []
        with DDGS() as ddgs:
            raw_results = list(ddgs.text(query, max_results=max_results))
            for r in raw_results:
                results.append({
                    "title": r.get("title", ""),
                    "snippet": r.get("body", ""),
                    "href": r.get("href", "")
                })
        if not results:
            return [{"title": "No results found", "snippet": f"No web results found for query: '{query}'", "href": ""}]
        return results
    except Exception as e:
        logger.warning(f"DuckDuckGo search error: {e}")
        # Fallback to Wikipedia if web search encounters network issue
        try:
            summary = wikipedia.summary(query, sentences=3)
            return [{"title": query, "snippet": summary, "href": "https://wikipedia.org"}]
        except Exception:
            return [{"error": f"Search could not be completed: {str(e)}"}]


@register_tool(
    name="get_wikipedia_summary",
    description="Look up encyclopedic information or quick definitions from Wikipedia.",
    parameters={
        "topic": {"type": "string", "description": "The topic, entity, or concept to look up", "required": True}
    }
)
def get_wikipedia_summary(topic: str) -> Dict[str, Any]:
    """Retrieve concise Wikipedia summary for a topic."""
    try:
        summary = wikipedia.summary(topic, sentences=4)
        page = wikipedia.page(topic, auto_suggest=False)
        return {
            "topic": page.title,
            "summary": summary,
            "url": page.url
        }
    except wikipedia.exceptions.DisambiguationError as e:
        # Pick the first suggested option
        try:
            first_opt = e.options[0]
            summary = wikipedia.summary(first_opt, sentences=3)
            return {
                "topic": first_opt,
                "summary": summary,
                "note": f"Multiple matches found. Showing top result for '{first_opt}'."
            }
        except Exception:
            return {"error": f"Topic '{topic}' is ambiguous. Options: {', '.join(e.options[:5])}"}
    except Exception as e:
        return {"error": f"Wikipedia lookup failed: {str(e)}"}

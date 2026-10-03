import logging
import re
from datetime import datetime
from typing import Any, Dict, List, Optional

from jarvis.agents.base import BaseSubAgent
from jarvis.tools.search import search_web, get_wikipedia_summary
from jarvis.execution import execution
from jarvis.memory import memory
from jarvis.tools.files import create_document

logger = logging.getLogger(__name__)

class ResearchAgent(BaseSubAgent):
    """
    Research Sub-Agent:
    - Multi-angle query formulation
    - Information gathering (web, wikipedia, page scraping)
    - Synthesis and executive reporting with sources
    - Semantic indexing of research findings
    """

    def __init__(self):
        super().__init__(
            name="ResearchAgent",
            role="Deep Information Researcher",
            description="Conducts multi-step deep research across web, Wikipedia, and articles, synthesizing structured findings."
        )

    def run(self, task: str, context: Optional[Dict[str, Any]] = None) -> Dict[str, Any]:
        logger.info(f"[{self.name}] Initiating research on: '{task}'")
        from jarvis.core.llm import llm

        # Step 1: Query Wikipedia for foundational encyclopedic context
        wiki_res = get_wikipedia_summary(task)
        wiki_summary = wiki_res.get("summary", "") if isinstance(wiki_res, dict) and "summary" in wiki_res else ""

        # Step 2: Search web for fresh sources
        web_results = search_web(task, max_results=4)
        snippets = []
        sources = []

        if isinstance(web_results, list):
            for item in web_results[:3]:
                if isinstance(item, dict):
                    title = item.get("title", "")
                    snip = item.get("snippet", "")
                    href = item.get("href", "")
                    if title and snip:
                        snippets.append(f"Title: {title}\nSnippet: {snip}")
                        if href:
                            sources.append(href)

        # Step 3: Fetch in-depth article content if top source link is available
        deep_content = ""
        if sources:
            top_url = sources[0]
            if top_url.startswith("http"):
                page_fetch = execution.browser.fetch_page_text(top_url, max_chars=2000)
                if page_fetch.get("success"):
                    deep_content = page_fetch.get("content", "")

        # Step 4: Synthesize using LLM or local template
        compiled_sources = "\n\n".join(snippets)
        synthesis_prompt = f"""You are a specialized Research Agent. Synthesize an objective, insightful research brief on the topic: '{task}'.

Encyclopedic Background:
{wiki_summary or 'N/A'}

Web Search Findings:
{compiled_sources or 'N/A'}

Article Excerpt:
{deep_content[:1000] if deep_content else 'N/A'}

Provide:
1. Executive Summary
2. Key Takeaways / Points
3. Current Context or Implications
Keep it concise, clear, and professional.
"""
        report_text = ""
        if llm.is_ollama_active() or llm.is_gemini_active():
            try:
                if llm.is_gemini_active():
                    resp = llm._genai_client.models.generate_content(
                        model=llm.model_name,
                        contents=synthesis_prompt
                    )
                    report_text = resp.text
                elif llm.is_ollama_active():
                    from jarvis.core.llm import ask_ollama
                    report_text = ask_ollama(synthesis_prompt, model=llm.ollama_model, url=llm.ollama_url)
            except Exception as e:
                logger.warning(f"LLM research synthesis failed ({e}). Using local collation.")

        if not report_text:
            report_text = f"# Research Brief: {task}\n\n"
            if wiki_summary:
                report_text += f"### Overview\n{wiki_summary}\n\n"
            if snippets:
                report_text += "### Key Web Findings\n" + "\n\n".join(f"- {s}" for s in snippets) + "\n\n"
            if sources:
                report_text += "### Sources\n" + "\n".join(f"- {u}" for u in sources)

        # Step 5: Save research document
        clean_name = re.sub(r"[^\w\-]", "_", task.lower())[:30]
        filename = f"research_{clean_name}.md"
        doc_res = create_document(filename, report_text)

        # Step 6: Index in Semantic Memory
        memory.semantic.add_entry(
            content=f"Research on '{task}': {report_text[:400]}...",
            source="research_agent",
            metadata={"topic": task, "filename": filename}
        )

        return {
            "success": True,
            "topic": task,
            "summary": report_text,
            "document": doc_res.get("filename"),
            "sources": sources,
            "wiki_found": bool(wiki_summary),
            "message": f"Research on '{task}' completed and compiled into '{filename}'."
        }

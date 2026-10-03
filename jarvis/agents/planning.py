import json
import logging
from typing import Any, Dict, List, Optional

from jarvis.agents.base import BaseSubAgent
from jarvis.tools.registry import registry
from jarvis.memory import memory

logger = logging.getLogger(__name__)

class PlanningAgent(BaseSubAgent):
    """
    Planning Sub-Agent:
    - Multi-step goal decomposition
    - Step-by-step sequential execution
    - Dynamic re-planning and contingency handling
    - Milestone tracking
    """

    def __init__(self):
        super().__init__(
            name="PlanningAgent",
            role="Strategic Task Planner & Orchestrator",
            description="Deconstructs complex goals into actionable multi-step execution plans and monitors completion."
        )

    def generate_plan(self, goal: str) -> List[Dict[str, Any]]:
        """
        Deconstruct goal into concrete steps.
        Uses LLM or rule-based decomposition.
        """
        from jarvis.core.llm import llm

        tools_summary = ", ".join(registry.get_all_tools().keys())
        prompt = f"""You are a Master Planner Agent. Deconstruct the following goal into 2 to 5 actionable steps.

Goal: "{goal}"

Available Tools: {tools_summary}

Respond ONLY with a valid JSON array of step objects in this exact format:
[
  {{
    "step_id": 1,
    "description": "Clear description of action",
    "tool_name": "exact_tool_name_or_none",
    "args": {{}}
  }}
]
"""
        steps = []
        if llm.is_ollama_active() or llm.is_gemini_active():
            try:
                raw_json = ""
                if llm.is_gemini_active():
                    resp = llm._genai_client.models.generate_content(
                        model=llm.model_name,
                        contents=prompt
                    )
                    raw_json = resp.text
                elif llm.is_ollama_active():
                    from jarvis.core.llm import ask_ollama
                    raw_json = ask_ollama(prompt, model=llm.ollama_model, url=llm.ollama_url)

                if raw_json:
                    import re
                    match = re.search(r"\[.*\]", raw_json, re.DOTALL)
                    if match:
                        steps = json.loads(match.group(0))
            except Exception as e:
                logger.warning(f"LLM plan generation failed: {e}")

        # Fallback plan if LLM not available or returned invalid JSON
        if not steps:
            steps = [
                {
                    "step_id": 1,
                    "description": f"Gather context and initial data for '{goal}'",
                    "tool_name": "search_web" if "search" in goal.lower() or "find" in goal.lower() else "get_system_status",
                    "args": {"query": goal} if "search" in goal.lower() else {}
                },
                {
                    "step_id": 2,
                    "description": f"Synthesize and log findings for '{goal}'",
                    "tool_name": "create_document",
                    "args": {"filename": "plan_summary.txt", "content": f"Plan execution summary for: {goal}"}
                }
            ]

        return steps

    def run(self, task: str, context: Optional[Dict[str, Any]] = None) -> Dict[str, Any]:
        logger.info(f"[{self.name}] Initiating plan for: '{task}'")
        memory.short_term.set_goal(task)

        # Generate plan
        steps = self.generate_plan(task)
        executed_steps = []
        overall_success = True

        for step in steps:
            s_id = step.get("step_id")
            desc = step.get("description")
            tool_name = step.get("tool_name")
            args = step.get("args", {})

            step_record = {
                "step_id": s_id,
                "description": desc,
                "tool_name": tool_name,
                "status": "pending"
            }

            if tool_name and tool_name in registry.get_all_tools():
                try:
                    res = registry.execute(tool_name, **args)
                    step_record["status"] = "success" if res.get("success") else "failed"
                    step_record["result"] = res.get("result")
                except Exception as e:
                    step_record["status"] = "error"
                    step_record["error"] = str(e)
                    overall_success = False
            else:
                step_record["status"] = "completed_note"
                step_record["result"] = f"Processed: {desc}"

            executed_steps.append(step_record)

        summary_msg = f"Plan executed for '{task}'. {len(executed_steps)} steps processed."
        memory.short_term.set_scratchpad("last_plan_results", executed_steps)

        return {
            "success": overall_success,
            "goal": task,
            "steps": executed_steps,
            "message": summary_msg
        }

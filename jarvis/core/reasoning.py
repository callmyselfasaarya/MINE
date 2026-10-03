import logging
import re
from typing import Any, Dict, Optional, Tuple

from jarvis.perception import perception
from jarvis.memory import memory

logger = logging.getLogger(__name__)

class ReasoningEngine:
    """
    Reasoning Engine for Jarvis Core:
    - Intent & Decision Analysis
    - Sub-Agent delegation detection (Research, Coding, Planning)
    - Perception context resolution (Screen, Camera, OCR, Sensors)
    - ReAct decision flow (Thought -> Action -> Observation -> Answer)
    """

    def analyze_intent(self, text: str) -> Dict[str, Any]:
        """
        Analyze user input to determine:
        1. Whether to delegate to a specialized Sub-Agent (research, coding, planning)
        2. Whether perception is needed (screen inspection, camera, OCR, sensors)
        3. Intent classification type
        """
        lower = text.lower().strip()

        # ── 1. Perception Triggers ───────────────────────────────────────────
        if any(w in lower for w in ["what's on my screen", "what is on my screen", "read screen", "screen text", "ocr screen"]):
            return {
                "decision": "perception_ocr",
                "target": "screen_ocr",
                "thought": "User wants text extracted from the current screen display."
            }

        if any(w in lower for w in ["look at my screen", "analyze my screen", "describe my screen", "inspect screen"]):
            return {
                "decision": "perception_vision",
                "target": "screen_vision",
                "thought": "User wants a visual multimodal analysis of their screen."
            }

        if any(w in lower for w in ["take a photo", "camera snapshot", "look at me", "check camera", "webcam"]):
            return {
                "decision": "perception_vision",
                "target": "camera_capture",
                "thought": "User wants a snapshot from the connected camera."
            }

        # ── 1B. Capabilities & Skills ────────────────────────────────────────
        if any(w in lower for w in [
            "what are the capabilities", "what are your capabilities", "tell me your capabilities",
            "list capabilities", "show capabilities", "what can you do", "what do you do",
            "what are your features", "what are your skills", "what are you capable of",
            "tell me what you can do", "what are all the things you can do"
        ]):
            return {
                "decision": "capabilities",
                "target": "capabilities",
                "thought": "User is asking for an overview of assistant capabilities."
            }

        # ── 2. Specialized Sub-Agent Triggers ───────────────────────────────
        # Research Agent
        if (
            lower.startswith("research ")
            or lower.startswith("deep dive into ")
            or lower.startswith("investigate ")
            or "comprehensive research on" in lower
            or "prepare a report on" in lower
        ):
            topic = re.sub(r"^(?:research|deep dive into|investigate|prepare a report on)\s+", "", text, flags=re.IGNORECASE).strip()
            return {
                "decision": "sub_agent",
                "agent_type": "research",
                "task": topic or text,
                "thought": f"Delegating deep multi-source investigation to ResearchAgent: '{topic}'"
            }

        # Coding Agent
        if (
            lower.startswith("write code")
            or lower.startswith("write a script")
            or lower.startswith("write python")
            or lower.startswith("code a ")
            or "debug this code" in lower
            or "run this code" in lower
            or "execute python" in lower
            or "```python" in lower
        ):
            return {
                "decision": "sub_agent",
                "agent_type": "coding",
                "task": text,
                "thought": "Delegating programming and code synthesis/testing to CodingAgent."
            }

        # Planning Agent
        if (
            lower.startswith("plan ")
            or lower.startswith("create a plan")
            or lower.startswith("how should i plan")
            or "step by step plan" in lower
            or "orchestrate a plan" in lower
        ):
            goal = re.sub(r"^(?:plan|create a plan for|how should i plan)\s+", "", text, flags=re.IGNORECASE).strip()
            return {
                "decision": "sub_agent",
                "agent_type": "planning",
                "task": goal or text,
                "thought": f"Deconstructing complex goal with PlanningAgent: '{goal}'"
            }

        # ── 3. Standard Core / Tool / Conversational Routing ────────────────
        return {
            "decision": "core_processing",
            "target": None,
            "thought": "Standard core processing via LLM and registered tools."
        }

    def execute_perception_decision(self, decision_info: Dict[str, Any]) -> Dict[str, Any]:
        """Fulfill a perception request."""
        target = decision_info.get("target")
        if target == "screen_ocr":
            ocr_res = perception.ocr.read_screen_text()
            if ocr_res.get("success"):
                text_content = ocr_res.get("text", "")
                preview = text_content[:500] if text_content else "No visible text detected."
                return {
                    "text": f"Here is the text extracted from your screen:\n\n{preview}",
                    "details": ocr_res,
                    "status": "success",
                    "provider": "perception_ocr"
                }
            return {
                "text": f"Could not extract screen text: {ocr_res.get('error', 'OCR unavailable')}",
                "status": "error"
            }

        elif target == "screen_vision":
            vis_res = perception.inspect_visual_context()
            desc = vis_res.get("analysis", {}).get("description", "Analyzed screen.")
            return {
                "text": f"Visual screen inspection: {desc}",
                "details": vis_res,
                "status": "success",
                "provider": "perception_vision"
            }

        elif target == "camera_capture":
            cam_res = perception.vision.capture_camera_frame()
            if cam_res.get("success"):
                return {
                    "text": f"Captured camera frame saved as '{cam_res.get('filename')}'.",
                    "details": cam_res,
                    "status": "success",
                    "provider": "perception_vision"
                }
            return {
                "text": f"Camera capture could not be completed: {cam_res.get('error')}",
                "status": "error"
            }

        return {"text": "Perception action completed.", "status": "success"}

# Global singleton
reasoning_engine = ReasoningEngine()

__all__ = ["ReasoningEngine", "reasoning_engine"]

import json
import logging
from typing import Any, Callable, Dict, List, Optional

from jarvis.config import ASSISTANT_NAME, USER_NAME
from jarvis.core.conversation import ConversationManager
from jarvis.core.guardrails import guardrails
from jarvis.core.llm import llm
from jarvis.core.reasoning import reasoning_engine
from jarvis.core.planner import planning_engine
from jarvis.perception import perception
from jarvis.memory import memory
from jarvis.execution import execution
from jarvis.voice.tts import speak
from jarvis.voice.stt import listen
from jarvis.voice.arbiter import voice_arbiter

logger = logging.getLogger(__name__)

class JarvisAgent:
    """
    Central Jarvis Core Orchestrator implementing the full Assistant Architecture:
    - USER / WORLD: Voice, Text, Camera, Files, Sensors, Apps
    - PERCEPTION: STT, Vision, OCR, Sensors
    - JARVIS CORE: LLM + Reasoning Engine, Planning + Decisions
    - MEMORY: Short-term (working context), Long-term (facts), Semantic (retrieval)
    - TOOLS: Browser, Computer, APIs
    - AGENTS: Research, Coding, Planning
    - ACTION / EXECUTION: PC, Browser, Smart Home, Apps & APIs
    """

    def __init__(self):
        self.name = ASSISTANT_NAME
        self.user_name = USER_NAME
        self.conversation = ConversationManager()
        self.guardrails = guardrails
        self.llm = llm
        self.perception = perception
        self.memory = memory
        self.reasoning = reasoning_engine
        self.planner = planning_engine
        self._agents = None
        self.execution = execution

        # Listeners for UI / WebSocket state updates
        self.event_listeners: List[Callable[[Dict[str, Any]], None]] = []

    @property
    def agents(self):
        if self._agents is None:
            from jarvis.agents import agents_manager
            self._agents = agents_manager
        return self._agents

    def register_event_listener(self, callback: Callable[[Dict[str, Any]], None]):
        if callback not in self.event_listeners:
            self.event_listeners.append(callback)

    def _broadcast_event(self, event_type: str, data: Dict[str, Any]):
        payload = {"event": event_type, "data": data}
        for listener in self.event_listeners:
            try:
                listener(payload)
            except Exception as e:
                logger.error(f"Event broadcast failed: {e}")

    def interact(self, user_text: str, speak_output: bool = True) -> Dict[str, Any]:
        """
        Complete perception-reasoning-action lifecycle:
        1. Receive User text/voice
        2. Analyze reasoning and routing (Sub-Agents / Perception / Core LLM)
        3. Execute action or delegated agent
        4. Update short-term & semantic memories
        5. Speak & broadcast response
        """
        if not user_text or not user_text.strip():
            return {"text": "", "status": "empty"}

        logger.info(f"User [{self.user_name}]: {user_text}")
        self._broadcast_event("user_speech", {"text": user_text})

        # ── 1. Reasoning Engine Intent & Decision Analysis ───────────────────
        analysis = self.reasoning.analyze_intent(user_text)
        decision = analysis.get("decision")
        thought = analysis.get("thought", "")

        self._broadcast_event("reasoning_step", {
            "thought": thought,
            "decision": decision,
            "analysis": analysis
        })

        # ── 2A. Sub-Agent Delegation (Research, Coding, Planning) ────────────
        if decision == "sub_agent":
            agent_type = analysis.get("agent_type", "")
            task = analysis.get("task", user_text)
            self._broadcast_event("subagent_dispatch", {"agent": agent_type, "task": task})

            agent_result = self.agents.dispatch(agent_type, task)
            summary_msg = agent_result.get("message") or agent_result.get("summary") or agent_result.get("response") or "Task executed."

            self.conversation.add_user_message(user_text)
            self.conversation.add_assistant_message(summary_msg)

            self._broadcast_event("agent_response", {"text": summary_msg, "result": agent_result})
            if speak_output and summary_msg:
                speak(summary_msg)

            return {
                "text": summary_msg,
                "subagent": agent_type,
                "details": agent_result,
                "status": "success",
                "provider": f"agent_{agent_type}"
            }

        # ── 2B. Direct Perception Request (Screen OCR, Vision, Camera) ───────
        elif decision and decision.startswith("perception_"):
            perc_result = self.reasoning.execute_perception_decision(analysis)
            resp_text = perc_result.get("text", "Perception captured.")

            self.conversation.add_user_message(user_text)
            self.conversation.add_assistant_message(resp_text)

            self._broadcast_event("agent_response", {"text": resp_text, "result": perc_result})
            if speak_output and resp_text:
                speak(resp_text)

            return perc_result

        # ── 2C. Direct Capabilities Request ─────────────────────────────────
        elif decision == "capabilities":
            from jarvis.tools.system import list_capabilities
            cap_res = list_capabilities()
            resp_text = cap_res.get("message", "I can assist you with voice, vision, screen OCR, apps, smart home, and agents.")

            self.conversation.add_user_message(user_text)
            self.conversation.add_assistant_message(resp_text)

            self._broadcast_event("agent_response", {"text": resp_text, "result": cap_res})
            if speak_output and resp_text:
                speak(resp_text)

            return {
                "text": resp_text,
                "tool_called": "list_capabilities",
                "tool_args": {},
                "tool_result": cap_res,
                "status": "success",
                "provider": "core_capabilities"
            }

        # ── 2D. Standard Core LLM / Intent Processing ────────────────────────
        result = self.llm.process(user_text, self.conversation)

        # Broadcast tool execution if any
        if result.get("tool_called"):
            self._broadcast_event("tool_call", {
                "name": result.get("tool_called"),
                "args": result.get("tool_args"),
                "result": result.get("tool_result"),
                "requires_confirmation": result.get("requires_confirmation", False)
            })

        response_text = result.get("text", "")
        logger.info(f"{self.name}: {response_text}")
        self._broadcast_event("agent_response", {"text": response_text, "result": result})

        # Speak response if requested
        if speak_output and response_text:
            speak(response_text)

        return result

    def voice_turn(self, timeout: float = 6.0) -> Optional[Dict[str, Any]]:
        """Listen to microphone and respond."""
        self._broadcast_event("listening_start", {})
        heard_text = listen(timeout=timeout)
        self._broadcast_event("listening_end", {"text": heard_text})

        if not heard_text:
            return None

        return self.interact(heard_text, speak_output=True)

    def confirm_action(self) -> Dict[str, Any]:
        """User authorizes the pending dangerous action."""
        res = self.guardrails.confirm()
        msg = f"Action authorized, Sir. {res.get('result', {}).get('message', 'Completed.')}"
        self.conversation.add_assistant_message(msg)
        speak(msg)
        self._broadcast_event("action_confirmed", {"result": res, "message": msg})
        return {"success": True, "message": msg, "details": res}

    def cancel_action(self) -> Dict[str, Any]:
        """User rejects the pending action."""
        res = self.guardrails.cancel()
        msg = res.get("message", "Action aborted.")
        self.conversation.add_assistant_message(msg)
        speak(msg)
        self._broadcast_event("action_cancelled", {"message": msg})
        return {"success": True, "message": msg}

    def get_dashboard_state(self) -> Dict[str, Any]:
        """Fetch current comprehensive system state for HUD dashboard."""
        from jarvis.tools.reminders import list_reminders
        from jarvis.tools.calendar import list_calendar_events
        from jarvis.core.memory import recall_facts
        from jarvis.tools.files import list_files

        try:
            sys_info = self.perception.sensors.get_hardware_telemetry()
            env_info = self.perception.sensors.get_environment_telemetry()
        except Exception:
            sys_info = {}
            env_info = {}

        try:
            reminders_data = list_reminders(include_completed=False).get("reminders", [])
        except Exception:
            reminders_data = []

        try:
            calendar_data = list_calendar_events().get("events", [])
        except Exception:
            calendar_data = []

        try:
            memories_data = recall_facts().get("results", [])
        except Exception:
            memories_data = []

        try:
            docs_data = list_files().get("items", [])
        except Exception:
            docs_data = []

        try:
            smart_devices = self.execution.smart_home.list_devices().get("devices", {})
        except Exception:
            smart_devices = {}

        pending = self.guardrails.get_pending_action()
        pending_data = None
        if pending:
            pending_data = {
                "action_id": pending.action_id,
                "tool_name": pending.tool_name,
                "args": pending.args,
                "prompt_message": pending.prompt_message
            }

        llm_info = self.llm.get_status_info()
        voice_info = voice_arbiter.get_status()

        return {
            "assistant_name": self.name,
            "user_name": self.user_name,
            "llm_info": llm_info,
            "provider": llm_info["provider"],
            "active_label": llm_info["active_label"],
            "gemini_active": self.llm.is_gemini_active(),
            "model_name": self.llm.ollama_model if self.llm.provider == "ollama" else self.llm.model_name,
            "system_status": sys_info,
            "environment_status": env_info,
            "smart_home_devices": smart_devices,
            "sub_agents": self.agents.list_agents(),
            "active_plan": self.planner.get_active_plan(),
            "semantic_memory_count": self.memory.semantic.count(),
            "reminders": reminders_data,
            "calendar_events": calendar_data,
            "memories": memories_data,
            "documents": docs_data,
            "pending_confirmation": pending_data,
            "voice_state": voice_info,
            "is_system_speaking": voice_info["is_system_speaking"],
            "is_mic_listening": voice_info["is_mic_listening"],
        }


# Global agent instance
jarvis_agent = JarvisAgent()
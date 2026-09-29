import logging
from typing import Any, Callable, Dict, List, Optional

from jarvis.config import ASSISTANT_NAME, USER_NAME
from jarvis.core.conversation import ConversationManager
from jarvis.core.guardrails import guardrails
from jarvis.core.llm import llm
from jarvis.voice.tts import speak
from jarvis.voice.stt import listen

logger = logging.getLogger(__name__)

class JarvisAgent:
    def __init__(self):
        self.name = ASSISTANT_NAME
        self.user_name = USER_NAME
        self.conversation = ConversationManager()
        self.guardrails = guardrails
        self.llm = llm

        # Listeners for UI state updates
        self.event_listeners: List[Callable[[Dict[str, Any]], None]] = []

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
        Full lifecycle:
        User Text/Speech -> LLM -> Tool Call -> Confirmation -> Response -> TTS
        """
        if not user_text or not user_text.strip():
            return {"text": "", "status": "empty"}

        logger.info(f"User [{self.user_name}]: {user_text}")
        self._broadcast_event("user_speech", {"text": user_text})

        # Process through LLM / Intent Engine
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
        """Fetch current system state for HUD dashboard."""
        from jarvis.tools.system import get_system_status
        from jarvis.tools.reminders import list_reminders
        from jarvis.tools.calendar import list_calendar_events
        from jarvis.core.memory import recall_facts
        from jarvis.tools.files import list_files

        try:
            sys_info = get_system_status()
        except Exception:
            sys_info = {}

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

        pending = self.guardrails.get_pending_action()
        pending_data = None
        if pending:
            pending_data = {
                "action_id": pending.action_id,
                "tool_name": pending.tool_name,
                "args": pending.args,
                "prompt_message": pending.prompt_message
            }

        return {
            "assistant_name": self.name,
            "user_name": self.user_name,
            "gemini_active": self.llm.is_gemini_active(),
            "model_name": self.llm.model_name,
            "system_status": sys_info,
            "reminders": reminders_data,
            "calendar_events": calendar_data,
            "memories": memories_data,
            "documents": docs_data,
            "pending_confirmation": pending_data
        }


# Global agent instance
jarvis_agent = JarvisAgent()
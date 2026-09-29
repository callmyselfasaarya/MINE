import json
import logging
import re
from typing import Any, Dict, List, Optional, Tuple

from jarvis.config import GEMINI_API_KEY, GEMINI_MODEL, ASSISTANT_NAME, USER_NAME
from jarvis.tools.registry import registry
from jarvis.core.guardrails import guardrails

logger = logging.getLogger(__name__)


class LocalIntentEngine:
    """Fallback rule-based natural language intent parser for offline or keyless operation."""

    def parse(self, text: str) -> Optional[Tuple[str, Dict[str, Any]]]:
        clean = text.strip()
        lower = clean.lower()

        # 1. Reminders
        # e.g.: "Jarvis, remind me tomorrow at 8 AM to submit my project"
        # e.g.: "remind me in 10 minutes to call Sarah"
        # e.g.: "set a reminder to buy groceries tomorrow at 5 PM"
        remind_match = re.search(
            r"remind\s+(?:me\s+)?(?:(tomorrow\s+at\s+[^to]+|today\s+at\s+[^to]+|in\s+\d+\s*(?:mins?|minutes?|hours?|secs?)|at\s+\d+(?::\d+)?\s*(?:am|pm)?)\s+)?(?:to\s+)?(.+)",
            lower,
            re.IGNORECASE
        )
        if remind_match:
            time_part = remind_match.group(1)
            task_part = remind_match.group(2)

            # Check if time is at the end: "remind me to [task] [time]"
            if not time_part:
                end_time_match = re.search(
                    r"(.+?)\s+(tomorrow(?:\s+at\s+[^$]+)?|in\s+\d+\s*(?:mins?|minutes?|hours?)|at\s+\d+(?::\d+)?\s*(?:am|pm)?)$",
                    task_part
                )
                if end_time_match:
                    task_part = end_time_match.group(1)
                    time_part = end_time_match.group(2)
                else:
                    time_part = "in 1 hour"

            # Clean task part
            task_part = re.sub(r"^(to\s+)", "", task_part).strip()
            return "create_reminder", {"title": task_part, "due_time": time_part}

        if any(p in lower for p in ["list reminders", "show reminders", "what are my reminders", "pending reminders"]):
            return "list_reminders", {"include_completed": False}

        # 2. Memory
        if any(p in lower for p in ["what do you remember", "list memories", "recall memories", "show memory", "do you remember"]):
            q = ""
            for p in ["what do you remember about", "do you remember", "recall memories about"]:
                if p in lower:
                    q = lower.split(p)[-1].strip().rstrip("?")
            return "recall_facts", {"query": q}

        # "remember that my car is blue", "remember my favorite food is sushi"
        mem_match = re.search(r"remember\s+(?:that\s+)?(?:my\s+)?([^is]+?)\s+is\s+(.+)", lower)
        if mem_match:
            topic = mem_match.group(1).strip()
            val = mem_match.group(2).strip()
            return "remember_fact", {"topic_or_key": topic, "information": val, "category": "preference"}

        mem_match2 = re.search(r"remember\s+(?:that\s+)?(.+)", lower)
        if mem_match2 and not lower.startswith("remember to"):
            info = mem_match2.group(1).strip()
            return "remember_fact", {"topic_or_key": "general_note", "information": info, "category": "notes"}

        # 3. System actions & Telemetry
        if any(p in lower for p in ["system status", "computer status", "system stats", "battery level", "cpu usage", "ram usage", "how is my pc", "how's my computer"]):
            return "get_system_status", {}

        if any(p in lower for p in ["take a screenshot", "capture screen", "screenshot"]):
            return "take_screenshot", {}

        open_app_match = re.search(r"(?:open|launch|start)\s+(?:the\s+)?(calculator|notepad|chrome|edge|browser|terminal|cmd|task manager|taskmgr|vscode|code|paint)", lower)
        if open_app_match:
            app = open_app_match.group(1)
            return "open_application", {"app_name": app}

        # Media controls
        if "mute" in lower:
            return "control_media", {"action": "mute"}
        if "volume up" in lower:
            return "control_media", {"action": "volumeup"}
        if "volume down" in lower:
            return "control_media", {"action": "volumedown"}
        if any(p in lower for p in ["pause music", "pause video", "play music", "play video", "resume playback"]):
            return "control_media", {"action": "playpause"}

        # 4. Search & Wikipedia
        search_match = re.search(r"(?:search\s+(?:the\s+web\s+for|for|google|ddg)?|lookup|look\s+up)\s+(.+)", lower)
        if search_match:
            q = search_match.group(1).strip()
            return "search_web", {"query": q}

        wiki_match = re.search(r"(?:who is|what is|tell me about|wikipedia)\s+(.+)", lower)
        if wiki_match:
            topic = wiki_match.group(1).strip().rstrip("?")
            if not any(k in topic for k in ["you", "your name", "the time", "today"]):
                return "get_wikipedia_summary", {"topic": topic}

        # 5. Documents & Files
        doc_create_match = re.search(r"(?:create|write|make)\s+(?:a\s+)?(?:document|file|note)\s+(?:called|named\s+)?([a-zA-Z0-9_\-\.]+)\s+(?:with\s+content\s+|containing\s+)?(.+)", clean, re.IGNORECASE)
        if doc_create_match:
            fname = doc_create_match.group(1).strip()
            content = doc_create_match.group(2).strip()
            if not fname.endswith((".txt", ".md", ".json")):
                fname += ".txt"
            return "create_document", {"filename": fname, "content": content}

        read_file_match = re.search(r"(?:read|view|show|display)\s+(?:the\s+)?(?:file|document|note)\s+([a-zA-Z0-9_\-\.\/\\]+)", lower)
        if read_file_match:
            f = read_file_match.group(1)
            return "read_file", {"filepath": f}

        if any(p in lower for p in ["list files", "show my files", "my documents", "list documents"]):
            return "list_files", {"directory": ""}

        # 6. Calendar
        cal_add_match = re.search(r"(?:schedule|add\s+(?:to\s+)?calendar|set\s+meeting)\s+(.+?)\s+(?:on|for)\s+([a-zA-Z0-9\s\-]+?)\s+at\s+([0-9:\sAPMapm]+)", lower)
        if cal_add_match:
            title = cal_add_match.group(1)
            date_s = cal_add_match.group(2)
            time_s = cal_add_match.group(3)
            return "create_calendar_event", {"title": title, "date_str": date_s, "time_str": time_s}

        if any(p in lower for p in ["calendar", "what's on my calendar", "upcoming events", "my schedule"]):
            return "list_calendar_events", {}

        # 7. Dangerous Actions (Testing confirmations)
        del_file_match = re.search(r"(?:delete|remove)\s+(?:the\s+)?(?:file|document)\s+([a-zA-Z0-9_\-\.\/\\]+)", lower)
        if del_file_match:
            f = del_file_match.group(1)
            return "delete_file", {"filepath": f}

        if any(p in lower for p in ["shutdown pc", "turn off computer", "shutdown system"]):
            return "system_power", {"action": "shutdown"}

        if any(p in lower for p in ["lock screen", "lock workstation", "lock pc"]):
            return "system_power", {"action": "lock"}

        return None


class LLMClient:
    def __init__(self):
        self.local_engine = LocalIntentEngine()
        self.api_key = GEMINI_API_KEY
        self.model_name = GEMINI_MODEL
        self._genai_client = None

        if self.api_key:
            try:
                from google import genai
                self._genai_client = genai.Client(api_key=self.api_key)
                logger.info(f"Initialized Gemini client with model {self.model_name}")
            except Exception as e:
                logger.error(f"Failed to initialize Gemini client: {e}")
                self._genai_client = None

    def reload_key(self, new_key: str):
        """Update API key at runtime if user sets it in HUD."""
        self.api_key = new_key.strip()
        if self.api_key:
            try:
                from google import genai
                self._genai_client = genai.Client(api_key=self.api_key)
                logger.info("Gemini API client re-initialized with new key.")
                return True
            except Exception as e:
                logger.error(f"Failed reinitializing Gemini: {e}")
        return False

    def is_gemini_active(self) -> bool:
        return self._genai_client is not None and bool(self.api_key)

    def process(
        self,
        user_text: str,
        conversation_manager
    ) -> Dict[str, Any]:
        """
        Main pipeline: Speech-to-text -> LLM -> Tool Call -> Confirmation -> Response
        """
        clean_text = user_text.strip()
        lower = clean_text.lower()

        # Step 0: Check if waiting for pending confirmation
        if guardrails.has_pending_action():
            if any(affirm in lower for affirm in ["yes", "confirm", "proceed", "authorize", "do it", "sure", "ok", "go ahead"]):
                res = guardrails.confirm()
                msg = f"Action authorized, Sir. {res.get('result', {}).get('message', 'Completed successfully.')}"
                conversation_manager.add_user_message(clean_text)
                conversation_manager.add_assistant_message(msg)
                return {
                    "text": msg,
                    "tool_called": res.get("tool_name"),
                    "tool_result": res,
                    "status": "confirmed",
                    "requires_confirmation": False
                }
            elif any(neg in lower for neg in ["no", "cancel", "abort", "stop", "don't", "negative", "nevermind"]):
                res = guardrails.cancel()
                msg = res.get("message", "Action aborted.")
                conversation_manager.add_user_message(clean_text)
                conversation_manager.add_assistant_message(msg)
                return {
                    "text": msg,
                    "status": "cancelled",
                    "requires_confirmation": False
                }
            else:
                pending = guardrails.get_pending_action()
                msg = f"I am still waiting for your authorization for '{pending.tool_name}'. Please say 'yes' to confirm or 'no' to abort."
                return {
                    "text": msg,
                    "status": "requires_confirmation",
                    "pending_action": pending.tool_name,
                    "requires_confirmation": True
                }

        # Step 1: Add user message to conversation history
        conversation_manager.add_user_message(clean_text)

        # Step 2: Try Gemini API if key is present
        if self.is_gemini_active():
            try:
                return self._process_with_gemini(clean_text, conversation_manager)
            except Exception as e:
                logger.warning(f"Gemini API execution error: {e}. Falling back to local intent parser.")

        # Step 3: Fallback to Local Intent Parser
        return self._process_with_local_intent(clean_text, conversation_manager)

    def _process_with_gemini(self, user_text: str, conversation_manager) -> Dict[str, Any]:
        from google.genai import types

        declarations = registry.get_gemini_declarations()
        gemini_tools = [types.Tool(function_declarations=declarations)] if declarations else None

        # Build contents from conversation history
        system_instruction = conversation_manager.get_system_instruction()
        history_msgs = conversation_manager.get_messages()

        contents = []
        for msg in history_msgs:
            role = "user" if msg["role"] == "user" else "model"
            contents.append(types.Content(
                role=role,
                parts=[types.Part.from_text(text=msg.get("content", ""))]
            ))

        config = types.GenerateContentConfig(
            system_instruction=system_instruction,
            tools=gemini_tools,
            temperature=0.7
        )

        response = self._genai_client.models.generate_content(
            model=self.model_name,
            contents=contents,
            config=config
        )

        # Check for function call
        if response.function_calls:
            fn_call = response.function_calls[0]
            tool_name = fn_call.name
            args = dict(fn_call.args) if fn_call.args else {}

            logger.info(f"Gemini proposed tool call: {tool_name} with args {args}")

            # Safety guardrail check
            safety_check = guardrails.check_tool_safety(tool_name, args)
            if safety_check:
                msg = safety_check["message"]
                conversation_manager.add_assistant_message(msg)
                return {
                    "text": msg,
                    "tool_called": tool_name,
                    "tool_args": args,
                    "status": "requires_confirmation",
                    "requires_confirmation": True,
                    "action_id": safety_check["action_id"],
                    "provider": "gemini"
                }

            # Execute tool
            exec_result = registry.execute(tool_name, **args)
            res_val = exec_result.get("result")

            # Format friendly natural response
            tool_def = registry.get_tool(tool_name)
            if isinstance(res_val, dict) and "confirmation" in res_val:
                reply = res_val["confirmation"]
            elif isinstance(res_val, dict) and "message" in res_val:
                reply = f"Done, Sir. {res_val['message']}"
            else:
                reply = f"I've executed {tool_name}. Result: {json.dumps(res_val)[:300]}"

            conversation_manager.add_tool_interaction(tool_name, args, res_val)
            conversation_manager.add_assistant_message(reply)

            return {
                "text": reply,
                "tool_called": tool_name,
                "tool_args": args,
                "tool_result": res_val,
                "status": "success",
                "requires_confirmation": False,
                "provider": "gemini"
            }

        # Plain text answer
        reply = response.text or "Standing by, Sir."
        conversation_manager.add_assistant_message(reply)
        return {
            "text": reply,
            "tool_called": None,
            "status": "success",
            "requires_confirmation": False,
            "provider": "gemini"
        }

    def _process_with_local_intent(self, user_text: str, conversation_manager) -> Dict[str, Any]:
        parsed = self.local_engine.parse(user_text)

        if not parsed:
            # Polite conversational response
            lower = user_text.lower()
            if any(h in lower for h in ["hello", "hi", "hey", "mine", "jarvis"]):
                reply = f"Greetings, {USER_NAME}. I am online and at your service. How may I assist you today?"
            elif any(w in lower for w in ["who are you", "what are you"]):
                reply = f"I am {ASSISTANT_NAME}, your personal desktop assistant. Version 1 MVP is active."
            elif any(t in lower for t in ["what time is it", "current time", "what is the time"]):
                from datetime import datetime
                reply = f"The time is currently {datetime.now().strftime('%I:%M %p')}."
            elif any(d in lower for d in ["what date is it", "today's date", "what day is it"]):
                from datetime import datetime
                reply = f"Today is {datetime.now().strftime('%A, %B %d, %Y')}."
            else:
                reply = f"I heard you, {USER_NAME}: \"{user_text}\". You can ask me to set reminders, search the web, manage calendar, check system stats, or create documents."

            conversation_manager.add_assistant_message(reply)
            return {
                "text": reply,
                "tool_called": None,
                "status": "success",
                "requires_confirmation": False,
                "provider": "local_intent"
            }

        tool_name, args = parsed
        logger.info(f"Local Intent recognized tool: {tool_name} with args {args}")

        # Check safety guardrails
        safety_check = guardrails.check_tool_safety(tool_name, args)
        if safety_check:
            msg = safety_check["message"]
            conversation_manager.add_assistant_message(msg)
            return {
                "text": msg,
                "tool_called": tool_name,
                "tool_args": args,
                "status": "requires_confirmation",
                "requires_confirmation": True,
                "action_id": safety_check["action_id"],
                "provider": "local_intent"
            }

        # Execute tool
        exec_result = registry.execute(tool_name, **args)
        res_val = exec_result.get("result")

        # Natural formatting for the specific user example:
        # You: "Jarvis, remind me tomorrow at 8 AM to submit my project."
        # JARVIS: "Done. I've set a reminder for tomorrow at 8 AM."
        if tool_name == "create_reminder" and isinstance(res_val, dict):
            reply = res_val.get("confirmation", f"Done. I've set a reminder for {args.get('title')} at {args.get('due_time')}.")
        elif tool_name == "create_calendar_event" and isinstance(res_val, dict):
            reply = res_val.get("message", "Done. I've scheduled the event on your calendar.")
        elif tool_name == "remember_fact" and isinstance(res_val, dict):
            reply = res_val.get("message", "I have remembered that for you, Sir.")
        elif tool_name == "get_system_status" and isinstance(res_val, dict):
            reply = f"System telemetry: {res_val.get('status_summary', 'Normal operation.')}"
        elif tool_name == "search_web" and isinstance(res_val, list):
            top = res_val[0] if res_val else {}
            reply = f"Here is what I found for '{args.get('query')}': {top.get('snippet', top.get('title', ''))}"
        elif tool_name == "get_wikipedia_summary" and isinstance(res_val, dict):
            reply = res_val.get("summary", "No summary found.")
        elif isinstance(res_val, dict) and "message" in res_val:
            reply = f"Done, Sir. {res_val['message']}"
        else:
            reply = f"Executed {tool_name}. Result: {json.dumps(res_val)[:200]}"

        conversation_manager.add_tool_interaction(tool_name, args, res_val)
        conversation_manager.add_assistant_message(reply)

        return {
            "text": reply,
            "tool_called": tool_name,
            "tool_args": args,
            "tool_result": res_val,
            "status": "success",
            "requires_confirmation": False,
            "provider": "local_intent"
        }


# Global LLM instance
llm = LLMClient()
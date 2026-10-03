import json
import logging
import re
import time
from typing import Any, Dict, List, Optional, Tuple
import requests
from jarvis.config import (
    GEMINI_API_KEY,
    GEMINI_MODEL,
    ASSISTANT_NAME,
    USER_NAME,
    LLM_PROVIDER,
    OLLAMA_HOST,
    OLLAMA_URL,
    OLLAMA_MODEL,
    OLLAMA_TIMEOUT
)
from jarvis.tools.registry import registry
from jarvis.core.guardrails import guardrails

logger = logging.getLogger(__name__)


def ask_ollama(message: str, model: str = OLLAMA_MODEL, url: str = OLLAMA_URL) -> str:
    """
    Direct standalone helper to query Ollama local LLM chat endpoint.
    User -> Python Assistant -> Ollama -> Local LLM -> Assistant -> User
    """
    response = requests.post(
        url,
        json={
            "model": model,
            "messages": [{"role": "user", "content": message}],
            "stream": False
        },
        timeout=(2.0, OLLAMA_TIMEOUT)
    )
    response.raise_for_status()
    data = response.json()
    return data["message"]["content"]


def format_tool_result_naturally(tool_name: str, args: Dict[str, Any], res_val: Any) -> str:
    """Format any tool execution result into polite, natural spoken English, never raw JSON."""
    if isinstance(res_val, dict):
        if "confirmation" in res_val and res_val["confirmation"]:
            return res_val["confirmation"]
        if "message" in res_val and res_val["message"]:
            return res_val["message"]
        if "summary" in res_val and res_val["summary"]:
            return res_val["summary"]
        if "description" in res_val and res_val["description"]:
            return res_val["description"]
        if "status_summary" in res_val:
            return f"System telemetry: {res_val['status_summary']}"
        if "output" in res_val:
            return f"The result is: {res_val['output']}"
    if isinstance(res_val, list):
        if tool_name == "search_web" and res_val:
            top = res_val[0]
            if isinstance(top, dict):
                return f"Here is what I found: {top.get('snippet', top.get('title', ''))}"
        return f"Completed {tool_name.replace('_', ' ')}. Found {len(res_val)} item(s)."
    if isinstance(res_val, str) and res_val:
        return res_val
    return f"Completed {tool_name.replace('_', ' ')} successfully for you, {USER_NAME}."


class LocalIntentEngine:
    """Fallback rule-based natural language intent parser for offline or keyless operation."""

    def parse(self, text: str) -> Optional[Tuple[str, Dict[str, Any]]]:
        clean = text.strip()
        lower = clean.lower()

        # ── 0. Greeting ──────────────────────────────────────────────────────
        if any(p in lower for p in [
            "good morning", "good afternoon", "good evening", "good night",
            "greet me", "say hello", "introduce yourself"
        ]):
            return "greet_user", {}

        # Standalone greetings (only if very short)
        if lower.strip().rstrip("!").rstrip(".") in (
            "hi", "hello", "hey", "hola", "howdy", "hey mine", "hi mine",
            "hello mine", "hey jarvis", "hello jarvis", "hi jarvis", "greetings"
        ):
            return "greet_user", {}

        # ── 0B. Capabilities & Skills ────────────────────────────────────────
        if any(p in lower for p in [
            "what are the capabilities", "what are your capabilities", "tell me your capabilities",
            "list capabilities", "show capabilities", "what can you do", "what do you do",
            "what are your features", "what are your skills", "what are you capable of",
            "tell me what you can do", "what can i do", "what are my options"
        ]):
            return "list_capabilities", {"category": "general"}

        # ── 1. Time & Date ───────────────────────────────────────────────────
        # (handled in conversational fallback, no dedicated tool needed)

        # ── 2. Jokes ─────────────────────────────────────────────────────────
        if any(p in lower for p in [
            "tell me a joke", "say a joke", "tell a joke", "joke please",
            "make me laugh", "say something funny", "tell something funny",
            "give me a joke", "crack a joke", "funny joke"
        ]):
            return "tell_joke", {}

        # ── 3. Play Music ────────────────────────────────────────────────────
        # "play music", "play some music", "play [song name]", "open spotify"
        play_music_match = re.search(
            r"(?:play|start|listen to|put on)\s+(?:some\s+)?(?:music|song|songs|tracks?)?(?:\s+by|\s+from|\s+called)?\s*(.*)$",
            lower
        )
        if play_music_match and any(p in lower for p in [
            "play music", "play song", "play songs", "play track", "listen to music",
            "put on music", "start music", "play some", "shuffle music"
        ]):
            q = play_music_match.group(1).strip()
            return "play_music", {"query": q}

        # "play [song/artist name]"
        specific_song_match = re.search(r"^(?:play|listen to|put on)\s+(.+)$", lower)
        if specific_song_match and not any(p in lower for p in [
            "play music", "play video", "play game"
        ]):
            song_q = specific_song_match.group(1).strip()
            # Make sure it's not already caught by app/website patterns
            if len(song_q) > 2:
                return "play_music", {"query": song_q}

        if "spotify" in lower:
            return "play_music", {"query": "spotify", "source": "spotify"}

        if "youtube music" in lower:
            return "play_music", {"query": "", "source": "youtube"}

        # ── 4. Open Website ──────────────────────────────────────────────────
        # "open youtube.com", "go to reddit.com", "open https://..."
        website_match = re.search(
            r"(?:open|go to|visit|navigate to|browse to)\s+((?:https?://)?[\w\-]+(?:\.[a-z]{2,})+(?:/[^\s]*)?)\b",
            lower
        )
        if website_match:
            url_candidate = website_match.group(1).strip()
            # If it contains a dot and looks like a URL, open as website
            if "." in url_candidate and not url_candidate.endswith("."):
                return "open_website", {"url": url_candidate}

        # ── 5. Google Search ─────────────────────────────────────────────────
        google_match = re.search(
            r"(?:search(?:\s+on)?\s+google\s+(?:for)?|google(?:\s+for)?|google\s+search(?:\s+for)?)\s+(.+)",
            lower
        )
        if google_match:
            q = google_match.group(1).strip()
            return "search_google", {"query": q}

        # ── 6. Screenshot with optional custom filename ───────────────────────
        screenshot_match = re.search(
            r"(?:take\s+a?\s*screenshot|capture\s+(?:the\s+)?screen|screenshot)(?:\s+(?:and\s+)?(?:save\s+(?:it\s+)?(?:as|with\s+name|named?|called?)?|name\s+it|filename?)\s+([\w\-\.]+))?[\s.]*$",
            lower
        )
        if screenshot_match:
            fname = screenshot_match.group(1)
            if fname:
                return "take_screenshot", {"filename": fname}
            return "take_screenshot", {}

        # ── 7. Save Note ──────────────────────────────────────────────────────
        note_match = re.search(
            r"(?:take\s+(?:a\s+)?(?:note|notes?)|save\s+(?:a\s+)?(?:note|notes?)|note\s+(?:this\s+)?(?:down)?|write\s+(?:a\s+)?note|add\s+(?:a\s+)?note|remember\s+(?:to\s+note)|jot\s+down)(?:\s+(?:that|:)?\s*)(.+)",
            lower
        )
        if note_match:
            note_text = note_match.group(1).strip()
            return "save_note", {"note": note_text}

        # ── 8. Reminders ──────────────────────────────────────────────────────
        remind_match = re.search(
            r"remind\s+(?:me\s+)?(?:(tomorrow\s+at\s+[^to]+|today\s+at\s+[^to]+|in\s+\d+\s*(?:mins?|minutes?|hours?|secs?)|at\s+\d+(?::\d+)?\s*(?:am|pm)?)\s+)?(?:to\s+)?(.+)",
            lower,
            re.IGNORECASE
        )
        if remind_match:
            time_part = remind_match.group(1)
            task_part = remind_match.group(2)

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

            task_part = re.sub(r"^(to\s+)", "", task_part).strip()
            return "create_reminder", {"title": task_part, "due_time": time_part}

        if any(p in lower for p in ["list reminders", "show reminders", "what are my reminders", "pending reminders"]):
            return "list_reminders", {"include_completed": False}

        # ── 9. Memory ─────────────────────────────────────────────────────────
        if any(p in lower for p in ["what do you remember", "list memories", "recall memories", "show memory", "do you remember"]):
            q = ""
            for p in ["what do you remember about", "do you remember", "recall memories about"]:
                if p in lower:
                    q = lower.split(p)[-1].strip().rstrip("?")
            return "recall_facts", {"query": q}

        mem_match = re.search(r"remember\s+(?:that\s+)?(?:my\s+)?([^is]+?)\s+is\s+(.+)", lower)
        if mem_match:
            topic = mem_match.group(1).strip()
            val = mem_match.group(2).strip()
            return "remember_fact", {"topic_or_key": topic, "information": val, "category": "preference"}

        mem_match2 = re.search(r"remember\s+(?:that\s+)?(.+)", lower)
        if mem_match2 and not lower.startswith("remember to"):
            info = mem_match2.group(1).strip()
            return "remember_fact", {"topic_or_key": "general_note", "information": info, "category": "notes"}

        # ── 10. System Status ─────────────────────────────────────────────────
        if any(p in lower for p in ["system status", "computer status", "system stats", "battery level",
                                      "cpu usage", "ram usage", "how is my pc", "how's my computer",
                                      "pc health", "check system"]):
            return "get_system_status", {}

        # ── 11. Open Application ──────────────────────────────────────────────
        open_app_match = re.search(
            r"(?:open|launch|start)\s+(?:the\s+)?("
            r"calculator|notepad|chrome|edge|firefox|browser|terminal|cmd|powershell|"
            r"task manager|taskmgr|vscode|code|paint|word|excel|powerpoint|outlook|"
            r"file explorer|explorer|control panel|settings|discord|telegram|whatsapp|"
            r"steam|obs|vlc|winamp|spotify|skype|zoom|teams"
            r")",
            lower
        )
        if open_app_match:
            app = open_app_match.group(1)
            return "open_application", {"app_name": app}

        # ── 12. Media Controls ────────────────────────────────────────────────
        if any(p in lower for p in ["mute", "mute audio", "mute sound"]):
            return "control_media", {"action": "mute"}
        if any(p in lower for p in ["volume up", "increase volume", "louder"]):
            return "control_media", {"action": "volumeup"}
        if any(p in lower for p in ["volume down", "decrease volume", "quieter", "lower volume"]):
            return "control_media", {"action": "volumedown"}
        if any(p in lower for p in ["next song", "next track", "skip song", "skip track"]):
            return "control_media", {"action": "next"}
        if any(p in lower for p in ["previous song", "previous track", "prev song", "go back"]):
            return "control_media", {"action": "prev"}
        if any(p in lower for p in ["pause", "resume playback", "pause music", "pause video",
                                      "stop music", "stop video"]):
            return "control_media", {"action": "playpause"}

        # ── 13. Web Search (DuckDuckGo) ───────────────────────────────────────
        search_match = re.search(
            r"(?:search\s+(?:the\s+(?:web|internet)\s+for|for|ddg)?|lookup|look\s+up|find\s+(?:info\s+(?:on|about))?|web\s+search(?:\s+for)?)\s+(.+)",
            lower
        )
        if search_match:
            q = search_match.group(1).strip()
            return "search_web", {"query": q}

        # ── 14. Wikipedia ─────────────────────────────────────────────────────
        wiki_match = re.search(r"(?:who is|what is|tell me about|wikipedia(?:\s+about)?)\s+(.+)", lower)
        if wiki_match:
            topic = wiki_match.group(1).strip().rstrip("?")
            if not any(k in topic for k in ["you", "your name", "the time", "today", "mine"]):
                return "get_wikipedia_summary", {"topic": topic}

        # ── 15. Documents & Files ─────────────────────────────────────────────
        doc_create_match = re.search(
            r"(?:create|write|make)\s+(?:a\s+)?(?:document|file|note)\s+(?:called|named\s+)?([a-zA-Z0-9_\-\.]+)\s+(?:with\s+content\s+|containing\s+)?(.+)",
            clean, re.IGNORECASE
        )
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

        # ── 16. Calendar ──────────────────────────────────────────────────────
        cal_add_match = re.search(
            r"(?:schedule|add\s+(?:to\s+)?calendar|set\s+meeting)\s+(.+?)\s+(?:on|for)\s+([a-zA-Z0-9\s\-]+?)\s+at\s+([0-9:\sAPMapm]+)",
            lower
        )
        if cal_add_match:
            title = cal_add_match.group(1)
            date_s = cal_add_match.group(2)
            time_s = cal_add_match.group(3)
            return "create_calendar_event", {"title": title, "date_str": date_s, "time_str": time_s}

        if any(p in lower for p in ["calendar", "what's on my calendar", "upcoming events", "my schedule"]):
            return "list_calendar_events", {}

        # ── 17. Dangerous Actions ─────────────────────────────────────────────
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
        self.provider = LLM_PROVIDER
        self.ollama_url = OLLAMA_URL
        self.ollama_model = OLLAMA_MODEL
        self.ollama_timeout = OLLAMA_TIMEOUT
        self._last_ollama_check = 0.0
        self._ollama_online = False

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

    def configure(
        self,
        provider: Optional[str] = None,
        ollama_model: Optional[str] = None,
        ollama_url: Optional[str] = None,
        gemini_api_key: Optional[str] = None,
        gemini_model: Optional[str] = None
    ) -> Dict[str, Any]:
        """Update provider and model settings at runtime."""
        if provider:
            self.provider = provider.lower().strip()
        if ollama_model:
            self.ollama_model = ollama_model.strip()
        if ollama_url:
            self.ollama_url = ollama_url.strip()
            self._last_ollama_check = 0.0
        if gemini_model:
            self.model_name = gemini_model.strip()
        if gemini_api_key is not None:
            self.reload_key(gemini_api_key)

        return self.get_status_info()

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

    def is_ollama_active(self, force_refresh: bool = False) -> bool:
        """Fast cached check to verify if the Ollama daemon is reachable."""
        now = time.time()
        if not force_refresh and (now - self._last_ollama_check) < 4.0:
            return self._ollama_online

        self._last_ollama_check = now
        try:
            host = self.ollama_url.rsplit("/api/", 1)[0] if "/api/" in self.ollama_url else self.ollama_url.rsplit("/", 1)[0]
            resp = requests.get(f"{host}/api/tags", timeout=0.6)
            self._ollama_online = (resp.status_code == 200)
        except Exception:
            self._ollama_online = False
        return self._ollama_online

    def get_status_info(self) -> Dict[str, Any]:
        ollama_online = self.is_ollama_active()
        active_label = "LOCAL INTENT ENGINE"
        if self.provider == "ollama" and ollama_online:
            active_label = f"OLLAMA ({self.ollama_model})"
        elif self.provider == "gemini" and self.is_gemini_active():
            active_label = f"GEMINI ({self.model_name})"
        elif self.provider == "ollama" and not ollama_online:
            active_label = f"OLLAMA OFFLINE (FALLBACK ACTIVE)"

        return {
            "provider": self.provider,
            "ollama_active": ollama_online,
            "ollama_model": self.ollama_model,
            "ollama_url": self.ollama_url,
            "gemini_active": self.is_gemini_active(),
            "gemini_model": self.model_name,
            "active_label": active_label
        }

    def process(
        self,
        user_text: str,
        conversation_manager
    ) -> Dict[str, Any]:
        """
        Main pipeline: Speech-to-text -> LLM (Ollama/Gemini/Local) -> Tool Call -> Confirmation -> Response
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

        # Step 2: Try Ollama Local LLM
        if self.provider == "ollama":
            ollama_result = self._process_with_ollama(clean_text, conversation_manager)
            if ollama_result:
                return ollama_result

        # Step 3: Try Gemini API if provider is gemini or fallback
        if self.provider == "gemini" or (self.provider == "ollama" and self.is_gemini_active()):
            if self.is_gemini_active():
                try:
                    return self._process_with_gemini(clean_text, conversation_manager)
                except Exception as e:
                    logger.warning(f"Gemini API execution error: {e}. Falling back to local intent parser.")

        # Step 4: Fallback to built-in Local Intent Parser
        return self._process_with_local_intent(clean_text, conversation_manager)

    def _sanitize_to_natural_language(self, text: str, user_text: str = "") -> str:
        """Ensure any message returned to the user or spoken via TTS is natural human language."""
        if not text or not text.strip():
            return f"Standing by, {USER_NAME}."

        clean = text.strip()

        # Strip markdown json block fences
        if clean.startswith("```"):
            clean = re.sub(r"^```(?:json)?\s*", "", clean)
            clean = re.sub(r"\s*```$", "", clean).strip()

        # If it starts with { and ends with }, parse and convert to natural speech
        if clean.startswith("{") and clean.endswith("}"):
            try:
                data = json.loads(clean)
                if isinstance(data, dict):
                    # Check for direct message or explanation keys
                    for k in ("message", "response", "text", "answer", "content", "summary", "description"):
                        if k in data and isinstance(data[k], str) and data[k].strip():
                            return data[k].strip()

                    # Check for capability / tool keys
                    name = data.get("name") or data.get("tool") or data.get("function")
                    if name and "capabilit" in str(name).lower():
                        from jarvis.tools.system import list_capabilities
                        return list_capabilities().get("message", "I can assist you with voice, vision, screen OCR, apps, smart home, and agents.")

                    # Otherwise, translate the intent / parameters into natural language
                    params = data.get("parameters") or data.get("arguments") or data.get("args") or {}
                    if isinstance(params, dict) and params:
                        param_str = ", ".join(f"{k}: {v}" for k, v in params.items())
                        return f"Regarding your request for {name or user_text or 'assistance'}, I have noted: {param_str}."
                    elif name:
                        return f"I have processed your request for {str(name).replace('_', ' ')}, {USER_NAME}."
            except Exception:
                pass

        # If text contains raw json snippet, clean it up
        if '{"name":' in clean or '{"function":' in clean:
            clean = re.sub(r'\{[^{}]*(?:name|function)[^{}]*\}', '', clean).strip()
            if not clean:
                return f"I understand your request, {USER_NAME}. How would you like me to proceed?"

        return clean

    def _process_with_ollama(self, user_text: str, conversation_manager) -> Optional[Dict[str, Any]]:
        # Fast exit if daemon is unreachable to eliminate latency
        if not self.is_ollama_active():
            logger.debug("Ollama daemon is not reachable. Using fallback engine.")
            return None

        system_instruction = conversation_manager.get_system_instruction()
        messages = [{"role": "system", "content": system_instruction}]

        for msg in conversation_manager.get_messages():
            role = "user" if msg["role"] == "user" else "assistant"
            messages.append({"role": role, "content": msg.get("content", "")})

        tools = registry.get_ollama_declarations()
        payload = {
            "model": self.ollama_model,
            "messages": messages,
            "stream": False,
            "tools": tools
        }

        try:
            logger.info(f"Querying Ollama at {self.ollama_url} with model '{self.ollama_model}'...")
            req_timeout = (1.5, self.ollama_timeout)
            response = requests.post(self.ollama_url, json=payload, timeout=req_timeout)

            # If model does not support tools parameter (HTTP 400), retry standard chat
            if response.status_code == 400 and "tools" in payload:
                logger.warning(f"Ollama model '{self.ollama_model}' rejected tools parameter. Retrying standard chat...")
                payload.pop("tools")
                response = requests.post(self.ollama_url, json=payload, timeout=req_timeout)

            response.raise_for_status()
            data = response.json()
            msg_obj = data.get("message", {})

            # Check for tool_calls from Ollama
            tool_calls = msg_obj.get("tool_calls", [])
            if tool_calls:
                tc = tool_calls[0]
                fn = tc.get("function", {})
                tool_name = fn.get("name")
                tool_args = fn.get("arguments", {})
                if isinstance(tool_args, str):
                    try:
                        tool_args = json.loads(tool_args)
                    except Exception:
                        tool_args = {}

                logger.info(f"Ollama proposed tool call: {tool_name} with args {tool_args}")

                # Safety guardrail check
                safety_check = guardrails.check_tool_safety(tool_name, tool_args)
                if safety_check:
                    msg = safety_check["message"]
                    conversation_manager.add_assistant_message(msg)
                    return {
                        "text": msg,
                        "tool_called": tool_name,
                        "tool_args": tool_args,
                        "status": "requires_confirmation",
                        "requires_confirmation": True,
                        "action_id": safety_check["action_id"],
                        "provider": f"ollama ({self.ollama_model})"
                    }

                # Execute tool
                exec_result = registry.execute(tool_name, **tool_args)
                res_val = exec_result.get("result")
                reply = format_tool_result_naturally(tool_name, tool_args, res_val)

                conversation_manager.add_tool_interaction(tool_name, tool_args, res_val)
                conversation_manager.add_assistant_message(reply)

                return {
                    "text": reply,
                    "tool_called": tool_name,
                    "tool_args": tool_args,
                    "tool_result": res_val,
                    "status": "success",
                    "requires_confirmation": False,
                    "provider": f"ollama ({self.ollama_model})"
                }

            # Plain text response from Ollama
            raw_content = msg_obj.get("content", "").strip() or "Standing by, Sir."

            # Check if Ollama returned a raw JSON tool call inside text content
            cleaned_json = raw_content
            if cleaned_json.startswith("```"):
                cleaned_json = re.sub(r"^```(?:json)?\s*", "", cleaned_json)
                cleaned_json = re.sub(r"\s*```$", "", cleaned_json).strip()

            parsed_call = None
            if cleaned_json.startswith("{") and cleaned_json.endswith("}"):
                try:
                    parsed_call = json.loads(cleaned_json)
                except Exception:
                    parsed_call = None

            if isinstance(parsed_call, dict) and any(k in parsed_call for k in ("name", "function", "tool")):
                tool_name = parsed_call.get("name") or (parsed_call.get("function") if isinstance(parsed_call.get("function"), str) else parsed_call.get("function", {}).get("name"))
                tool_args = parsed_call.get("parameters") or parsed_call.get("arguments") or parsed_call.get("args") or {}
                if isinstance(tool_args, str):
                    try:
                        tool_args = json.loads(tool_args)
                    except Exception:
                        tool_args = {}

                # Check if tool is list_capabilities or in registry
                if tool_name == "list_capabilities" or (tool_name and "capabilit" in str(tool_name).lower()):
                    from jarvis.tools.system import list_capabilities
                    cap_res = list_capabilities(**tool_args) if isinstance(tool_args, dict) else list_capabilities()
                    reply = cap_res.get("message")
                    conversation_manager.add_assistant_message(reply)
                    return {
                        "text": reply,
                        "tool_called": "list_capabilities",
                        "tool_args": tool_args,
                        "tool_result": cap_res,
                        "status": "success",
                        "requires_confirmation": False,
                        "provider": f"ollama ({self.ollama_model})"
                    }

                if tool_name and tool_name in registry.get_all_tools():
                    logger.info(f"Executing embedded JSON tool call from Ollama: {tool_name}")
                    safety_check = guardrails.check_tool_safety(tool_name, tool_args)
                    if safety_check:
                        msg = safety_check["message"]
                        conversation_manager.add_assistant_message(msg)
                        return {
                            "text": msg,
                            "tool_called": tool_name,
                            "tool_args": tool_args,
                            "status": "requires_confirmation",
                            "requires_confirmation": True,
                            "action_id": safety_check["action_id"],
                            "provider": f"ollama ({self.ollama_model})"
                        }

                    exec_result = registry.execute(tool_name, **tool_args)
                    res_val = exec_result.get("result")
                    reply = format_tool_result_naturally(tool_name, tool_args, res_val)
                    conversation_manager.add_tool_interaction(tool_name, tool_args, res_val)
                    conversation_manager.add_assistant_message(reply)
                    return {
                        "text": reply,
                        "tool_called": tool_name,
                        "tool_args": tool_args,
                        "tool_result": res_val,
                        "status": "success",
                        "requires_confirmation": False,
                        "provider": f"ollama ({self.ollama_model})"
                    }
                else:
                    # Tool not in registry: re-query Ollama without tools for a natural conversation reply
                    logger.warning(f"Ollama returned unrecognized tool '{tool_name}' in JSON. Retrying in conversational mode...")
                    try:
                        retry_resp = requests.post(
                            self.ollama_url,
                            json={"model": self.ollama_model, "messages": messages, "stream": False},
                            timeout=req_timeout
                        )
                        if retry_resp.status_code == 200:
                            retry_content = retry_resp.json().get("message", {}).get("content", "").strip()
                            if retry_content and not (retry_content.startswith("{") and retry_content.endswith("}")):
                                raw_content = retry_content
                    except Exception as e:
                        logger.debug(f"Ollama conversational retry error: {e}")

            # Ensure response text is sanitized into natural spoken English
            reply = self._sanitize_to_natural_language(raw_content, user_text)
            conversation_manager.add_assistant_message(reply)
            return {
                "text": reply,
                "tool_called": None,
                "status": "success",
                "requires_confirmation": False,
                "provider": f"ollama ({self.ollama_model})"
            }

        except (requests.exceptions.ConnectionError, requests.exceptions.Timeout) as e:
            logger.warning(f"Ollama server not reachable at {self.ollama_url} ({e}). Seamlessly falling back to local engine.")
            return None
        except Exception as e:
            logger.error(f"Ollama request error: {e}. Falling back to local engine.")
            return None

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
            reply = format_tool_result_naturally(tool_name, args, res_val)

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
        reply = self._sanitize_to_natural_language(response.text or "Standing by, Sir.", user_text)
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
            from datetime import datetime
            lower = user_text.lower()
            now = datetime.now()

            # ── Handle built-in conversational shortcuts first ──────────────────
            if any(w in lower for w in ["who are you", "what are you", "what's your name", "your name"]):
                reply = (
                    f"I am {ASSISTANT_NAME}, your personal AI desktop assistant. "
                    f"I can open apps, search the web, play music, tell jokes, "
                    f"take notes, manage reminders, check system stats, and much more."
                )
                conversation_manager.add_assistant_message(reply)
                return {"text": reply, "tool_called": None, "status": "success",
                        "requires_confirmation": False, "provider": "local_intent"}

            elif any(t in lower for t in [
                "what time is it", "current time", "what is the time",
                "what's the time", "tell me the time", "time please"
            ]):
                reply = f"The current time is {now.strftime('%I:%M %p')}, {USER_NAME}."
                conversation_manager.add_assistant_message(reply)
                return {"text": reply, "tool_called": None, "status": "success",
                        "requires_confirmation": False, "provider": "local_intent"}

            elif any(d in lower for d in [
                "what date is it", "today's date", "what day is it",
                "what is today", "what's today", "current date"
            ]):
                reply = f"Today is {now.strftime('%A, %B %d, %Y')}, {USER_NAME}."
                conversation_manager.add_assistant_message(reply)
                return {"text": reply, "tool_called": None, "status": "success",
                        "requires_confirmation": False, "provider": "local_intent"}

            elif any(dt in lower for dt in ["date and time", "time and date"]):
                reply = f"It is {now.strftime('%A, %B %d, %Y')} and the time is {now.strftime('%I:%M %p')}, {USER_NAME}."
                conversation_manager.add_assistant_message(reply)
                return {"text": reply, "tool_called": None, "status": "success",
                        "requires_confirmation": False, "provider": "local_intent"}

            # ── Out-of-context: try Ollama for a free-form conversational answer ─
            if self.is_ollama_active():
                logger.info(f"Local intent engine returned None. Routing to Ollama for conversational answer: '{user_text}'")
                ollama_result = self._process_with_ollama(user_text, conversation_manager)
                if ollama_result:
                    # Tag it clearly so the CLI/HUD can show the Ollama label
                    ollama_result["provider"] = f"ollama ({self.ollama_model}) [conversational]"
                    return ollama_result

            # ── Last resort: offline generic reply ──────────────────────────────
            reply = (
                f"I heard you, {USER_NAME}: \"{user_text}\". "
                f"I can help you: greet you, tell the time/date, open apps & websites, "
                f"search Google/Wikipedia, play music, take notes, screenshot, tell jokes, "
                f"set reminders, and manage your calendar. "
                f"For general questions, make sure Ollama is running (`ollama serve`)."
            )
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

        # Natural language formatting per tool
        if tool_name == "greet_user" and isinstance(res_val, dict):
            reply = res_val.get("message", "Hello! How may I assist you?")
        elif tool_name == "tell_joke" and isinstance(res_val, dict):
            reply = f"{res_val.get('setup', '')} ... {res_val.get('punchline', '')}"
        elif tool_name == "play_music" and isinstance(res_val, dict):
            reply = res_val.get("message", "Playing music for you, Sir.")
        elif tool_name == "open_website" and isinstance(res_val, dict):
            reply = res_val.get("message", "Opened the website, Sir.")
        elif tool_name == "search_google" and isinstance(res_val, dict):
            reply = res_val.get("message", "Opened Google search, Sir.")
        elif tool_name == "save_note" and isinstance(res_val, dict):
            reply = res_val.get("message", "Note saved successfully, Sir.")
        elif tool_name == "create_reminder" and isinstance(res_val, dict):
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
        elif tool_name == "list_capabilities" and isinstance(res_val, dict):
            reply = res_val.get("message", "I can assist you with voice, vision, screen OCR, apps, smart home, and agents.")
        elif tool_name == "take_screenshot" and isinstance(res_val, dict):
            reply = f"Screenshot saved as '{res_val.get('filename', 'screenshot')}', Sir."
        elif isinstance(res_val, dict) and "message" in res_val:
            reply = f"Done, Sir. {res_val['message']}"
        else:
            reply = format_tool_result_naturally(tool_name, args, res_val)

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
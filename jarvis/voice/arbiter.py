"""
arbiter.py — Voice Arbiter & Source Differentiator for M.I.N.E.

Differentiates between System Voice (TTS, audio playback, assistant output)
and Microphone Voice (human user speaking into the microphone), preventing
acoustic feedback loops, self-triggering, barge-in confusion, and voice overlap.
"""

import difflib
import logging
import re
import threading
import time
from collections import deque
from typing import Any, Callable, Dict, List, Optional, Set, Tuple

from jarvis.config import (
    VOICE_ECHO_CANCELLATION,
    VOICE_ECHO_COOLDOWN,
    VOICE_ECHO_SIMILARITY_THRESHOLD,
    VOICE_ECHO_HISTORY_WINDOW,
    WAKE_WORD,
    WAKE_WORD_ALIASES,
)

logger = logging.getLogger(__name__)


def normalize_text(text: str) -> str:
    """Lowercase, strip punctuation, and normalize whitespace for phonetic/text comparison."""
    if not text:
        return ""
    t = text.lower().strip()
    t = re.sub(r"[^\w\s]", " ", t)
    return " ".join(t.split())


def extract_tokens(text: str) -> Set[str]:
    """Extract set of normalized words from text."""
    norm = normalize_text(text)
    return set(norm.split()) if norm else set()


class VoiceArbiter:
    """
    Coordinates and arbitrates between System Voice and Microphone Voice.

    Key responsibilities:
    1. Tracks real-time state: Is System Voice active (playing)? Is Mic Voice active (listening)?
    2. Maintains a sliding history window of recent system speech utterances with timestamps.
    3. Provides acoustic cooldown settling so speaker reverb in the room doesn't contaminate mic input.
    4. Differentiates microphone transcripts: classifies whether heard speech is a system voice echo
       or a genuine user utterance, preventing self-looping and overlapping responses.
    5. Dispatches state events to subscribed listeners (CLI, Web HUD, WebSocket).
    """

    def __init__(
        self,
        echo_cancellation: bool = VOICE_ECHO_CANCELLATION,
        echo_cooldown: float = VOICE_ECHO_COOLDOWN,
        similarity_threshold: float = VOICE_ECHO_SIMILARITY_THRESHOLD,
        history_window: float = VOICE_ECHO_HISTORY_WINDOW,
    ):
        self.echo_cancellation_enabled = echo_cancellation
        self.echo_cooldown = echo_cooldown
        self.similarity_threshold = similarity_threshold
        self.history_window = history_window

        self._lock = threading.RLock()
        self._speech_done_event = threading.Event()
        self._speech_done_event.set()  # Initially idle

        self._is_system_speaking = False
        self._is_mic_listening = False

        self._last_speech_start: float = 0.0
        self._last_speech_end: float = 0.0
        self._last_speech_text: str = ""

        # History of recent system speech utterances: list of dicts
        self._history: deque = deque(maxlen=30)

        # Registered state listeners: callback(event_type: str, data: Dict[str, Any])
        self._listeners: List[Callable[[str, Dict[str, Any]], None]] = []

        # Wake word triggers to detect assistant name / wake phrases in system utterances
        self._wake_triggers = [normalize_text(WAKE_WORD)] + [
            normalize_text(a) for a in WAKE_WORD_ALIASES if normalize_text(a)
        ]

        # Telemetry / metrics
        self.metrics = {
            "total_inputs_evaluated": 0,
            "system_echoes_filtered": 0,
            "user_voices_accepted": 0,
            "last_filtered_echo": "",
            "last_filter_reason": "",
        }

    # ── State Listener Registration ──────────────────────────────────────────

    def register_state_listener(self, callback: Callable[[str, Dict[str, Any]], None]) -> None:
        """Register a callback for voice state transitions (system_voice_start, system_voice_end, etc.)."""
        with self._lock:
            if callback not in self._listeners:
                self._listeners.append(callback)

    def _notify_listeners(self, event_type: str, data: Dict[str, Any]) -> None:
        listeners_copy = list(self._listeners)
        for cb in listeners_copy:
            try:
                cb(event_type, data)
            except Exception as e:
                logger.error(f"[VoiceArbiter] Listener callback error ({event_type}): {e}")

    # ── System Voice State Transitions ───────────────────────────────────────

    def notify_speech_start(self, text: str) -> None:
        """Notify that the system (TTS/speaker) has started outputting speech audio."""
        clean = text.strip() if text else ""
        norm = normalize_text(clean)
        words = norm.split()
        tokens = set(words)
        now = time.time()

        with self._lock:
            self._is_system_speaking = True
            self._speech_done_event.clear()
            self._last_speech_start = now
            self._last_speech_text = clean

            entry = {
                "text": clean,
                "normalized": norm,
                "words": words,
                "tokens": tokens,
                "start_time": now,
                "end_time": now + 0.5,  # initial estimate, updated in notify_speech_end
                "timestamp": now,
            }
            self._history.append(entry)

        logger.debug(f"[VoiceArbiter] System Voice START: '{clean[:50]}'")
        self._notify_listeners("system_voice_start", {"text": clean, "timestamp": now})

    def notify_speech_end(self) -> None:
        """Notify that the system (TTS/speaker) has finished outputting speech audio."""
        now = time.time()
        with self._lock:
            self._is_system_speaking = False
            self._last_speech_end = now
            self._speech_done_event.set()

            # Update the latest history entry's end_time
            if self._history:
                self._history[-1]["end_time"] = now

        logger.debug(f"[VoiceArbiter] System Voice END. Cooldown={self.echo_cooldown}s")
        self._notify_listeners("system_voice_end", {"timestamp": now, "cooldown": self.echo_cooldown})

    # ── Microphone Voice State Transitions ───────────────────────────────────

    def notify_listen_start(self) -> None:
        """Notify that the microphone has started recording audio from the user."""
        now = time.time()
        with self._lock:
            self._is_mic_listening = True
        logger.debug("[VoiceArbiter] Mic Voice START")
        self._notify_listeners("mic_listen_start", {"timestamp": now})

    def notify_listen_end(self) -> None:
        """Notify that the microphone has finished recording audio."""
        now = time.time()
        with self._lock:
            self._is_mic_listening = False
        logger.debug("[VoiceArbiter] Mic Voice END")
        self._notify_listeners("mic_listen_end", {"timestamp": now})

    # ── Status Inspection & Synchronization ──────────────────────────────────

    def is_system_speaking(self, include_cooldown: bool = False) -> bool:
        """
        Check if System Voice is active.
        If include_cooldown is True, returns True while speaking OR during the acoustic cooldown buffer.
        """
        with self._lock:
            if self._is_system_speaking:
                return True
            if include_cooldown and self._last_speech_end > 0:
                elapsed = time.time() - self._last_speech_end
                return elapsed < self.echo_cooldown
            return False

    def is_mic_listening(self) -> bool:
        """Check if Microphone Voice input is currently active."""
        with self._lock:
            return self._is_mic_listening

    def get_last_speech_text(self) -> str:
        with self._lock:
            return self._last_speech_text

    def wait_for_system_voice(self, timeout: float = 12.0, extra_cooldown: Optional[float] = None) -> bool:
        """
        Block until the System Voice has completely finished speaking and acoustic reverberation
        in the room has settled. Returns True if quiet, False if timed out.
        """
        # 1. Wait for active speech worker to finish speaking
        if self.is_system_speaking(include_cooldown=False):
            logger.debug("[VoiceArbiter] Waiting for active System Voice to finish speaking...")
            done = self._speech_done_event.wait(timeout=timeout)
            if not done:
                logger.warning("[VoiceArbiter] Timed out waiting for System Voice to finish speaking.")
                return False

        # 2. Wait for acoustic cooldown settling (room reverb / hardware buffer decay)
        cooldown = self.echo_cooldown if extra_cooldown is None else extra_cooldown
        with self._lock:
            last_end = self._last_speech_end

        if last_end > 0 and cooldown > 0:
            remaining = (last_end + cooldown) - time.time()
            if remaining > 0:
                time.sleep(remaining)

        return True

    # ── Source Differentiation & Echo Cancellation ───────────────────────────

    def differentiate_input(
        self,
        text: str,
        timestamp: Optional[float] = None,
    ) -> Dict[str, Any]:
        """
        Differentiate whether an audio transcript obtained from the microphone is:
        - 'system_voice': An acoustic reflection / echo of the assistant's own output.
        - 'user_voice': A genuine human user utterance from the microphone.

        Returns a dictionary with classification details:
        {
            "source": "system_voice" | "user_voice",
            "is_system_echo": bool,
            "confidence": float,
            "matched_phrase": Optional[str],
            "reason": str,
            "clean_text": str,
        }
        """
        now = timestamp or time.time()

        with self._lock:
            self.metrics["total_inputs_evaluated"] += 1

            if not text or not text.strip():
                return {
                    "source": "user_voice",
                    "is_system_echo": False,
                    "confidence": 1.0,
                    "matched_phrase": None,
                    "reason": "empty_input",
                    "clean_text": "",
                }

            if not self.echo_cancellation_enabled:
                self.metrics["user_voices_accepted"] += 1
                return {
                    "source": "user_voice",
                    "is_system_echo": False,
                    "confidence": 1.0,
                    "matched_phrase": None,
                    "reason": "echo_cancellation_disabled",
                    "clean_text": text.strip(),
                }

            input_clean = text.strip()
            input_norm = normalize_text(input_clean)
            input_words = input_norm.split()
            input_tokens = set(input_words)

            if not input_norm:
                return {
                    "source": "user_voice",
                    "is_system_echo": False,
                    "confidence": 1.0,
                    "matched_phrase": None,
                    "reason": "punctuation_only",
                    "clean_text": input_clean,
                }

            # Check if audio was captured while system was speaking or in acoustic cooldown
            is_during_speech = self._is_system_speaking or (
                self._last_speech_end > 0 and (now - self._last_speech_end) < self.echo_cooldown
            )

            # Prune old history entries beyond history_window
            valid_history = [
                entry for entry in self._history
                if (now - entry.get("timestamp", 0)) <= self.history_window
            ]

            # Compare against each recent system utterance
            for entry in reversed(valid_history):
                sys_text = entry["text"]
                sys_norm = entry["normalized"]
                sys_words = entry["words"]
                sys_tokens = entry["tokens"]

                if not sys_norm:
                    continue

                # ── Signature 1: Exact Match ─────────────────────────────────
                if input_norm == sys_norm:
                    return self._record_echo(
                        input_clean, sys_text, "exact_match", confidence=1.0
                    )

                # ── Signature 2: Substring Containment (Microphone captured fragment of system speech) ──
                # e.g., System said: "Good evening, Aarya. MINE is online and standing by."
                # Microphone heard: "online and standing by" or "mine is online"
                if input_norm in sys_norm:
                    # Require at least 2 words or a single word of >= 4 characters to avoid false hits on "a", "i"
                    if len(input_words) >= 2 or len(input_norm) >= 4:
                        conf = 0.98 if is_during_speech else 0.92
                        return self._record_echo(
                            input_clean, sys_text, "substring_of_system_speech", confidence=conf
                        )

                # ── Signature 3: Inverse Substring Containment ────────────────
                # e.g., System said short phrase "Yes?" or "System ready", mic heard "Oh yes" or "Yes system ready"
                if len(sys_words) >= 2 and sys_norm in input_norm:
                    conf = 0.95 if is_during_speech else 0.85
                    return self._record_echo(
                        input_clean, sys_text, "contains_system_speech", confidence=conf
                    )

                if len(sys_words) == 1 and sys_norm in input_norm and is_during_speech:
                    conf = 0.90
                    return self._record_echo(
                        input_clean, sys_text, "single_word_during_system_speech", confidence=conf
                    )

                # ── Signature 4: Sequence Similarity (difflib SequenceMatcher) ──
                ratio = difflib.SequenceMatcher(None, input_norm, sys_norm).ratio()
                threshold = self.similarity_threshold
                effective_thresh = (threshold - 0.10) if is_during_speech else threshold

                if ratio >= effective_thresh:
                    return self._record_echo(
                        input_clean, sys_text, f"similarity_ratio_{ratio:.2f}", confidence=ratio
                    )

                # ── Signature 5: Token Overlap & Coverage ─────────────────────
                if input_tokens and sys_tokens:
                    overlap = len(input_tokens & sys_tokens)
                    coverage = overlap / len(input_tokens)

                    # If at least 75% of user's words were in the system's utterance:
                    if len(input_words) >= 2 and coverage >= 0.75:
                        return self._record_echo(
                            input_clean, sys_text, f"token_coverage_{coverage:.2f}", confidence=coverage
                        )

                    # During active speech or cooldown, even 55% overlap indicates speech bleed
                    if is_during_speech and len(input_words) >= 2 and coverage >= 0.55:
                        return self._record_echo(
                            input_clean, sys_text, f"during_speech_overlap_{coverage:.2f}", confidence=coverage
                        )

                # ── Signature 6: System Wake Word Self-Trigger Bleed ───────────
                # If assistant spoke its own name / wake phrase and mic caught it
                if any(trig in input_norm for trig in self._wake_triggers):
                    if any(trig in sys_norm for trig in self._wake_triggers):
                        return self._record_echo(
                            input_clean, sys_text, "system_wake_word_bleed", confidence=0.95
                        )

                # ── Signature 7: Significant Word Bleed During Active Speech ───
                if is_during_speech and input_tokens and sys_tokens:
                    significant_common = [w for w in (input_tokens & sys_tokens) if len(w) >= 4]
                    if significant_common and len(input_words) <= 3:
                        return self._record_echo(
                            input_clean,
                            sys_text,
                            f"active_speech_word_bleed_{significant_common[0]}",
                            confidence=0.85,
                        )

            # Not an echo: Classified as genuine user microphone voice
            self.metrics["user_voices_accepted"] += 1
            return {
                "source": "user_voice",
                "is_system_echo": False,
                "confidence": 1.0,
                "matched_phrase": None,
                "reason": "user_input",
                "clean_text": input_clean,
            }

    def _record_echo(
        self,
        clean_text: str,
        matched_phrase: str,
        reason: str,
        confidence: float,
    ) -> Dict[str, Any]:
        """Record telemetry and return system echo classification result."""
        self.metrics["system_echoes_filtered"] += 1
        self.metrics["last_filtered_echo"] = clean_text
        self.metrics["last_filter_reason"] = reason

        logger.info(
            f"[VoiceArbiter] DIFFERENTIATED SYSTEM VOICE ECHO: '{clean_text}' "
            f"(matched system phrase: '{matched_phrase}', reason: {reason}, confidence: {confidence:.2f})"
        )

        return {
            "source": "system_voice",
            "is_system_echo": True,
            "confidence": confidence,
            "matched_phrase": matched_phrase,
            "reason": reason,
            "clean_text": clean_text,
        }

    # ── Telemetry & Diagnostics ──────────────────────────────────────────────

    def get_status(self) -> Dict[str, Any]:
        """Get diagnostic summary of Voice Arbiter status."""
        with self._lock:
            return {
                "is_system_speaking": self._is_system_speaking,
                "is_mic_listening": self._is_mic_listening,
                "echo_cancellation_enabled": self.echo_cancellation_enabled,
                "echo_cooldown": self.echo_cooldown,
                "similarity_threshold": self.similarity_threshold,
                "last_speech_text": self._last_speech_text,
                "history_count": len(self._history),
                "metrics": dict(self.metrics),
            }


# Global singleton instance
voice_arbiter = VoiceArbiter()

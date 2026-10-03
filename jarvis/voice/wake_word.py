"""
wake_word.py — Continuous background wake-word detection for M.I.N.E.

How it works
────────────
A daemon thread runs an infinite loop, capturing short audio bursts from
the microphone and checking whether the transcribed text contains the
configured wake phrase.  When the wake word is detected, all registered
callbacks are fired.  The main CLI / agent then handles the follow-up
listen → respond cycle.

Configuration (via .env)
────────────────────────
  WAKE_WORD=hey mine           # Phrase that activates the assistant
  WAKE_WORD_ENABLED=true       # Set to true to auto-start on launch
  WAKE_WORD_ALIASES=mine,jarvis,hey jarvis  # Extra aliases (comma-separated)
"""

import logging
import threading
import time
from typing import Callable, List, Optional

import speech_recognition as sr

from jarvis.config import (
    ASSISTANT_NAME,
    WAKE_WORD,
    WAKE_WORD_ALIASES,
    STT_ENERGY_THRESHOLD,
)
from jarvis.voice.arbiter import voice_arbiter

logger = logging.getLogger(__name__)

# ── Types ─────────────────────────────────────────────────────────────────────
WakeCallback = Callable[[str], None]  # receives the full utterance heard


class WakeWordEngine:
    """
    Continuously listens on the default microphone in a background thread.
    When a configured wake phrase is detected, all registered callbacks are invoked.

    Usage
    -----
    engine = WakeWordEngine()
    engine.on_wake(lambda phrase: print(f"Wake detected: {phrase}"))
    engine.start()
    ...
    engine.stop()
    """

    def __init__(
        self,
        wake_word: str = WAKE_WORD,
        aliases: Optional[List[str]] = None,
        listen_timeout: float = 3.0,
        phrase_time_limit: float = 5.0,
    ):
        self.wake_word = wake_word.lower().strip()
        self.aliases: List[str] = [a.lower().strip() for a in (aliases or WAKE_WORD_ALIASES)]
        # All phrases that count as a wake trigger
        self._triggers: List[str] = list({self.wake_word} | set(self.aliases))

        self.listen_timeout = listen_timeout
        self.phrase_time_limit = phrase_time_limit

        self._callbacks: List[WakeCallback] = []
        self._running = False
        self._thread: Optional[threading.Thread] = None
        self._paused = False          # Pause detection while assistant is responding

        self._recognizer = sr.Recognizer()
        self._recognizer.energy_threshold = STT_ENERGY_THRESHOLD
        self._recognizer.dynamic_energy_threshold = True
        self._recognizer.pause_threshold = 0.6

    # ── Public API ─────────────────────────────────────────────────────────────

    def on_wake(self, callback: WakeCallback) -> None:
        """Register a callback to be called when the wake word is detected."""
        if callback not in self._callbacks:
            self._callbacks.append(callback)

    def start(self) -> bool:
        """Start the background listener thread. Returns True if started successfully."""
        if self._running:
            logger.warning("Wake-word engine is already running.")
            return True
        try:
            # Quick mic sanity check before starting
            with sr.Microphone() as src:
                self._recognizer.adjust_for_ambient_noise(src, duration=0.3)
        except Exception as e:
            logger.error(f"Cannot start wake-word engine — microphone unavailable: {e}")
            return False

        self._running = True
        self._thread = threading.Thread(
            target=self._loop,
            daemon=True,
            name="MineWakeWordListener"
        )
        self._thread.start()
        logger.info(
            f"Wake-word engine started. Listening for: {self._triggers}"
        )
        return True

    def stop(self) -> None:
        """Stop the background listener thread."""
        self._running = False
        self._thread = None
        logger.info("Wake-word engine stopped.")

    def pause(self) -> None:
        """Temporarily pause detection (e.g. while assistant is speaking/responding)."""
        self._paused = True

    def resume(self) -> None:
        """Resume detection after a pause."""
        self._paused = False

    @property
    def is_running(self) -> bool:
        return self._running

    @property
    def is_paused(self) -> bool:
        return self._paused

    def set_wake_word(self, new_word: str) -> None:
        """Dynamically change the wake word at runtime."""
        self.wake_word = new_word.lower().strip()
        self._triggers = list({self.wake_word} | set(self.aliases))
        logger.info(f"Wake word updated to: {self._triggers}")

    # ── Internal ───────────────────────────────────────────────────────────────

    def _loop(self) -> None:
        """Main detection loop — runs in daemon thread."""
        logger.debug("Wake-word detection loop started.")
        while self._running:
            # Pause listening while assistant is speaking or acoustic cooldown is active
            if self._paused or voice_arbiter.is_system_speaking(include_cooldown=True):
                time.sleep(0.2)
                continue
            try:
                heard = self._capture_phrase()
                if not heard:
                    continue

                # Differentiate system voice from user voice: reject acoustic reflection
                diff = voice_arbiter.differentiate_input(heard)
                if diff["is_system_echo"]:
                    logger.info(
                        f"[Wake-word] Rejected system voice reflection: '{heard}' "
                        f"(matched: '{diff['matched_phrase']}', reason: {diff['reason']})"
                    )
                    continue

                if self._is_wake(heard):
                    logger.info(f"Wake word detected in: '{heard}'")
                    self.pause()   # Suppress re-trigger while handling
                    self._fire(heard)
            except Exception as e:
                logger.debug(f"Wake loop error (non-fatal): {e}")
                time.sleep(0.5)

    def _capture_phrase(self) -> Optional[str]:
        """Capture a short audio burst and transcribe it. Returns None on timeout."""
        try:
            with sr.Microphone() as source:
                audio = self._recognizer.listen(
                    source,
                    timeout=self.listen_timeout,
                    phrase_time_limit=self.phrase_time_limit,
                )
            text = self._recognizer.recognize_google(audio)
            return text.strip().lower()
        except (sr.WaitTimeoutError, sr.UnknownValueError):
            return None
        except sr.RequestError as e:
            logger.warning(f"STT service error during wake detection: {e}")
            time.sleep(2.0)
            return None

    def _is_wake(self, text: str) -> bool:
        """Return True if any configured trigger phrase appears in the heard text."""
        return any(trigger in text for trigger in self._triggers)

    def _fire(self, utterance: str) -> None:
        """Invoke all registered callbacks with the raw utterance."""
        for cb in self._callbacks:
            try:
                cb(utterance)
            except Exception as e:
                logger.error(f"Wake callback error: {e}")


# ── Global singleton ───────────────────────────────────────────────────────────
wake_engine = WakeWordEngine()

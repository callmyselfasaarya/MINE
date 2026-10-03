import logging
import queue
import threading
from typing import Callable, List, Optional
from jarvis.config import TTS_ENABLED, TTS_RATE, TTS_VOLUME
from jarvis.voice.arbiter import voice_arbiter

logger = logging.getLogger(__name__)

# Listeners that get notified when JARVIS speaks (e.g. WebSocket to frontend HUD)
_speech_listeners: List[Callable[[str], None]] = []


def register_speech_listener(callback: Callable[[str], None]):
    """Register a callback that receives every spoken text."""
    if callback not in _speech_listeners:
        _speech_listeners.append(callback)


class TTSEngine:
    def __init__(self):
        self.enabled = TTS_ENABLED
        self.queue: queue.Queue = queue.Queue()
        self.worker_thread = threading.Thread(target=self._worker, daemon=True, name="MineTTSWorker")
        self.speaker = None
        self._init_speaker()
        self.worker_thread.start()

    def _init_speaker(self):
        try:
            import pythoncom
            import win32com.client
            pythoncom.CoInitialize()
            self.speaker = win32com.client.Dispatch("SAPI.SpVoice")
            logger.info("Initialized Windows SAPI TTS engine.")
        except Exception as e:
            logger.warning(f"Could not initialize Windows SAPI engine directly: {e}. Web TTS will be used.")
            self.speaker = None

    def _worker(self):
        import pythoncom
        pythoncom.CoInitialize()
        while True:
            text = self.queue.get()
            if text is None:
                break
            try:
                # Notify Voice Arbiter that System Voice has begun output
                voice_arbiter.notify_speech_start(text)

                # Notify listeners (such as WebSocket client for browser speech synthesis)
                for cb in _speech_listeners:
                    try:
                        cb(text)
                    except Exception as ex:
                        logger.error(f"Error in speech listener callback: {ex}")

                # If local speaker is available and enabled, speak through host device
                if self.enabled and self.speaker:
                    try:
                        # 0 = Synchronous speak in background thread
                        self.speaker.Speak(text, 0)
                    except Exception as err:
                        logger.debug(f"Local audio device playback skipped ({err}). Spoken via Web HUD.")
            except Exception as e:
                logger.error(f"TTS Worker encountered an error: {e}")
            finally:
                # Notify Voice Arbiter that System Voice has finished output
                voice_arbiter.notify_speech_end()
                self.queue.task_done()

    def speak(self, text: str, block: bool = False, timeout: float = 15.0):
        """
        Speak the given text asynchronously or synchronously.
        When block=True, waits until the speech is complete and room acoustic reverb settles.
        """
        if not text or not text.strip():
            return
        clean_text = text.strip()
        self.queue.put(clean_text)
        if block:
            self.queue.join()
            voice_arbiter.wait_for_system_voice(timeout=timeout)

    def wait_until_done(self, timeout: float = 15.0) -> bool:
        """Wait until all queued and active system speech has finished playing."""
        self.queue.join()
        return voice_arbiter.wait_for_system_voice(timeout=timeout)

    @property
    def is_speaking(self) -> bool:
        """Check if system voice is actively speaking or in acoustic cooldown."""
        return voice_arbiter.is_system_speaking(include_cooldown=True)

    def stop(self):
        """Immediately abort active speech and clear the speech queue."""
        # Drain pending queue
        while not self.queue.empty():
            try:
                self.queue.get_nowait()
                self.queue.task_done()
            except queue.Empty:
                break
        # SVSFPurgeBeforeSpeak = 2 in SAPI purges current speech
        if self.speaker:
            try:
                self.speaker.Speak("", 2)
            except Exception as e:
                logger.debug(f"SAPI purge error: {e}")
        voice_arbiter.notify_speech_end()

    def set_enabled(self, enabled: bool):
        self.enabled = enabled


# Global instance
tts = TTSEngine()
speak = tts.speak


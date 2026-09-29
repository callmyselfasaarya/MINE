import logging
import queue
import threading
from typing import Callable, List, Optional
from jarvis.config import TTS_ENABLED, TTS_RATE, TTS_VOLUME

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
                self.queue.task_done()

    def speak(self, text: str, block: bool = False):
        """Speak the given text asynchronously or synchronously."""
        if not text or not text.strip():
            return
        clean_text = text.strip()
        self.queue.put(clean_text)
        if block:
            self.queue.join()

    def set_enabled(self, enabled: bool):
        self.enabled = enabled


# Global instance
tts = TTSEngine()
speak = tts.speak

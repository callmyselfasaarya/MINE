import logging
from typing import Optional
import speech_recognition as sr
from jarvis.config import STT_ENERGY_THRESHOLD, STT_PAUSE_THRESHOLD

logger = logging.getLogger(__name__)

class STTEngine:
    def __init__(self):
        self.recognizer = sr.Recognizer()
        self.recognizer.energy_threshold = STT_ENERGY_THRESHOLD
        self.recognizer.pause_threshold = STT_PAUSE_THRESHOLD
        self.recognizer.dynamic_energy_threshold = True

    def listen(self, timeout: float = 6.0, phrase_time_limit: float = 12.0) -> Optional[str]:
        """Listen to the default microphone and return transcribed text."""
        try:
            with sr.Microphone() as source:
                logger.info("Calibrating ambient noise...")
                self.recognizer.adjust_for_ambient_noise(source, duration=0.6)
                logger.info("Listening for speech...")
                audio = self.recognizer.listen(source, timeout=timeout, phrase_time_limit=phrase_time_limit)

            logger.info("Transcribing audio...")
            text = self.recognizer.recognize_google(audio)
            logger.info(f"Transcribed: '{text}'")
            return text.strip()
        except sr.WaitTimeoutError:
            logger.debug("Listening timed out waiting for speech.")
            return None
        except sr.UnknownValueError:
            logger.debug("Speech unintelligible.")
            return None
        except sr.RequestError as e:
            logger.error(f"Speech recognition service error: {e}")
            return None
        except Exception as e:
            logger.error(f"Microphone or STT error: {e}")
            return None


# Global STT instance
stt = STTEngine()
listen = stt.listen

import logging
from typing import Optional
from jarvis.voice.stt import listen, calibrate, stt
from jarvis.voice.arbiter import voice_arbiter

logger = logging.getLogger(__name__)

class STTPerception:
    """
    Speech-to-Text Perception Subsystem:
    - Hands-free microphone capture
    - Echo-cancellation and speech arbitration
    """

    def listen_speech(self, timeout: float = 6.0, phrase_time_limit: float = 12.0) -> Optional[str]:
        return listen(timeout=timeout, phrase_time_limit=phrase_time_limit)

    def calibrate_noise(self, duration: float = 1.0):
        calibrate(duration=duration)

    def get_status(self):
        return voice_arbiter.get_status()

import json
import logging
import urllib.request
import urllib.error
from typing import Any, Callable, Dict, List, Optional
import speech_recognition as sr

from jarvis.config import (
    STT_ENERGY_THRESHOLD,
    STT_PAUSE_THRESHOLD,
    STT_DYNAMIC_ENERGY,
    MIC_DEVICE_INDEX,
)

logger = logging.getLogger(__name__)


def _robust_recognize_google(
    recognizer: sr.Recognizer,
    audio_data: sr.AudioData,
    key: Optional[str] = None,
    language: str = "en-US",
    show_all: bool = False,
    **kwargs: Any,
) -> Any:
    """
    Direct, robust Google Speech Recognition using 16kHz linear 16-bit PCM.
    Completely eliminates dependency on external FLAC binaries (e.g. flac-win32.exe),
    preventing WinError 623 (Illegal System DLL Relocation) on modern 64-bit Windows.
    """
    if not isinstance(audio_data, sr.AudioData):
        raise ValueError("audio_data must be an AudioData instance")

    # Resample and convert to 16kHz 16-bit mono PCM in pure Python
    rate = 16000
    pcm_data = audio_data.get_raw_data(convert_rate=rate, convert_width=2)

    api_key = key or "AIzaSyBOti4mM-6x9WDnZIjIeyEU21OpBXqWBgw"
    url = f"https://www.google.com/speech-api/v2/recognize?client=chromium&lang={language}&key={api_key}"
    headers = {
        "Content-Type": f"audio/l16; rate={rate}",
        "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36",
    }

    req = urllib.request.Request(url, data=pcm_data, headers=headers)
    timeout = getattr(recognizer, "operation_timeout", None) or 10.0

    try:
        with urllib.request.urlopen(req, timeout=timeout) as resp:
            resp_text = resp.read().decode("utf-8")
    except urllib.error.URLError as e:
        raise sr.RequestError(f"Google Speech API network error: {e}")
    except Exception as e:
        raise sr.RequestError(f"Recognition request failed: {e}")

    for line in resp_text.strip().split("\n"):
        line = line.strip()
        if not line:
            continue
        try:
            data = json.loads(line)
            if "result" in data and data["result"]:
                alts = data["result"][0].get("alternative", [])
                if alts:
                    if show_all:
                        return data
                    return alts[0]["transcript"].strip()
        except json.JSONDecodeError:
            continue

    raise sr.UnknownValueError()


# Monkey-patch speech_recognition globally so all components (including wake_word) benefit
sr.Recognizer.recognize_google = _robust_recognize_google


class STTEngine:
    def __init__(self, device_index: Optional[int] = None):
        self.recognizer = sr.Recognizer()
        self.recognizer.energy_threshold = STT_ENERGY_THRESHOLD
        self.recognizer.pause_threshold = STT_PAUSE_THRESHOLD
        self.recognizer.dynamic_energy_threshold = STT_DYNAMIC_ENERGY
        self.recognizer.dynamic_energy_adjustment_damping = 0.15
        self.recognizer.dynamic_energy_ratio = 1.5

        if device_index is not None:
            self.device_index: Optional[int] = device_index
        else:
            self.device_index = MIC_DEVICE_INDEX if MIC_DEVICE_INDEX >= 0 else None

        self._calibrated = False
        self.last_error: Optional[str] = None

    def get_microphones(self) -> List[Dict[str, Any]]:
        """List all available microphone input devices."""
        mics = []
        try:
            names = sr.Microphone.list_microphone_names()
            for idx, name in enumerate(names):
                mics.append({"index": idx, "name": name})
        except Exception as e:
            logger.error(f"Error enumerating microphones: {e}")
        return mics

    def set_device_index(self, index: Optional[int]) -> None:
        """Switch active microphone device index."""
        self.device_index = index if (index is not None and index >= 0) else None
        self._calibrated = False
        logger.info(f"Microphone device set to index: {self.device_index}")

    def calibrate(self, duration: float = 0.3) -> None:
        """Calibrate ambient noise so subsequent listens start instantaneously without clipping voice."""
        try:
            with sr.Microphone(device_index=self.device_index) as source:
                logger.info("Calibrating ambient noise...")
                self.recognizer.adjust_for_ambient_noise(source, duration=duration)
                self._calibrated = True
                logger.info(f"Ambient noise calibrated. energy_threshold={self.recognizer.energy_threshold}")
        except Exception as e:
            logger.debug(f"Calibration notice: {e}")

    def listen(
        self,
        timeout: float = 6.0,
        phrase_time_limit: float = 15.0,
        on_ready: Optional[Callable[[], None]] = None
    ) -> Optional[str]:
        """Listen to the microphone and return transcribed text, or None if no speech."""
        self.last_error = None
        try:
            with sr.Microphone(device_index=self.device_index) as source:
                if not self._calibrated:
                    logger.info("Calibrating ambient noise once...")
                    self.recognizer.adjust_for_ambient_noise(source, duration=0.3)
                    self._calibrated = True

                if on_ready:
                    on_ready()

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
            logger.debug("Speech unintelligible / silence.")
            return None
        except sr.RequestError as e:
            msg = f"Speech recognition service error: {e}"
            logger.warning(msg)
            self.last_error = msg
            return None
        except Exception as e:
            msg = f"Microphone error: {e}"
            logger.error(msg)
            self.last_error = msg
            return None


# Global STT instance
stt = STTEngine()
listen = stt.listen
calibrate = stt.calibrate
get_microphones = stt.get_microphones

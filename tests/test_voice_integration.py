"""
Integration tests for Voice Differentiation across STT, TTS, and Wake Word modules.
"""

import time
import unittest
from unittest.mock import MagicMock, patch

from jarvis.voice.arbiter import voice_arbiter
from jarvis.voice.stt import STTEngine
from jarvis.voice.tts import TTSEngine


class TestVoiceIntegration(unittest.TestCase):

    def setUp(self):
        voice_arbiter._history.clear()
        voice_arbiter._is_system_speaking = False
        voice_arbiter._is_mic_listening = False
        voice_arbiter._last_speech_end = 0.0
        voice_arbiter.metrics = {
            "total_inputs_evaluated": 0,
            "system_echoes_filtered": 0,
            "user_voices_accepted": 0,
            "last_filtered_echo": "",
            "last_filter_reason": "",
        }

    def test_stt_filters_system_voice_echo(self):
        stt_engine = STTEngine()
        stt_engine._calibrated = True

        # System speaks
        voice_arbiter.notify_speech_start("The battery is at 95 percent and charging.")
        voice_arbiter.notify_speech_end()

        # Mock microphone capture to return audio
        with patch.object(stt_engine.recognizer, "listen", return_value=MagicMock()):
            with patch.object(stt_engine.recognizer, "recognize_google", return_value="battery is at 95 percent and charging"):
                with patch("speech_recognition.Microphone"):
                    result = stt_engine.listen(timeout=2.0, filter_echo=True, wait_for_system_voice=False)

                    # Should be filtered out as system voice echo!
                    self.assertIsNone(result)
                    self.assertIsNotNone(stt_engine.last_filtered_echo)
                    self.assertIn("battery is at 95 percent", stt_engine.last_filtered_echo)

    def test_stt_accepts_genuine_user_voice(self):
        stt_engine = STTEngine()
        stt_engine._calibrated = True

        # System speaks something unrelated
        voice_arbiter.notify_speech_start("Good morning, Sir.")
        voice_arbiter.notify_speech_end()

        # Mock microphone capture with genuine user command
        with patch.object(stt_engine.recognizer, "listen", return_value=MagicMock()):
            with patch.object(stt_engine.recognizer, "recognize_google", return_value="open chrome"):
                with patch("speech_recognition.Microphone"):
                    result = stt_engine.listen(timeout=2.0, filter_echo=True, wait_for_system_voice=False)

                    # Should be accepted as user voice!
                    self.assertEqual(result, "open chrome")
                    self.assertIsNone(stt_engine.last_filtered_echo)

    def test_tts_notifies_arbiter_properly(self):
        engine = TTSEngine()
        # Mock the speaker so it doesn't access actual audio hardware during tests
        engine.speaker = MagicMock()

        engine.speak("Testing Voice Arbiter synchronization.", block=True)

        # After block=True, speech must be complete
        self.assertFalse(voice_arbiter.is_system_speaking(include_cooldown=False))
        self.assertIn("Testing Voice Arbiter synchronization.", voice_arbiter.get_last_speech_text())


if __name__ == "__main__":
    unittest.main()

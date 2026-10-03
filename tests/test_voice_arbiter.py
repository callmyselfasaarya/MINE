"""
Unit tests for Voice Arbiter and System Voice vs Microphone Voice Differentiation.
"""

import time
import unittest

from jarvis.voice.arbiter import VoiceArbiter, normalize_text


class TestVoiceArbiter(unittest.TestCase):

    def setUp(self):
        # Create a fresh VoiceArbiter instance with standard parameters for isolated testing
        self.arbiter = VoiceArbiter(
            echo_cancellation=True,
            echo_cooldown=0.3,
            similarity_threshold=0.65,
            history_window=10.0,
        )

    def test_normalization(self):
        self.assertEqual(normalize_text("Hello, World!"), "hello world")
        self.assertEqual(normalize_text("   MINE is   Online...  "), "mine is online")
        self.assertEqual(normalize_text("What's up?!"), "what s up")

    def test_exact_match_echo_rejection(self):
        # System speaks
        self.arbiter.notify_speech_start("Good evening, Aarya. MINE is online and standing by.")
        self.arbiter.notify_speech_end()

        # Mic records the exact same text
        result = self.arbiter.differentiate_input("Good evening, Aarya. MINE is online and standing by.")
        self.assertTrue(result["is_system_echo"])
        self.assertEqual(result["source"], "system_voice")
        self.assertEqual(result["confidence"], 1.0)
        self.assertEqual(result["reason"], "exact_match")

    def test_substring_fragment_echo_rejection(self):
        # System speaks a sentence
        self.arbiter.notify_speech_start("I have added the meeting with Alex to your calendar.")
        self.arbiter.notify_speech_end()

        # Microphone captures a fragment of that sentence
        fragment = "meeting with Alex to your calendar"
        result = self.arbiter.differentiate_input(fragment)
        self.assertTrue(result["is_system_echo"])
        self.assertEqual(result["source"], "system_voice")
        self.assertEqual(result["reason"], "substring_of_system_speech")

    def test_short_system_utterance_contained_in_mic(self):
        # System says "Yes?"
        self.arbiter.notify_speech_start("Yes?")
        self.arbiter.notify_speech_end()

        # Mic captures "Yes"
        res1 = self.arbiter.differentiate_input("Yes")
        self.assertTrue(res1["is_system_echo"])

        # Mic captures "Oh yes" during active speech or cooldown
        self.arbiter.notify_speech_start("Yes?")
        res2 = self.arbiter.differentiate_input("Oh yes")
        self.assertTrue(res2["is_system_echo"])
        self.arbiter.notify_speech_end()

    def test_genuine_user_voice_preserved(self):
        # System says something
        self.arbiter.notify_speech_start("The current CPU load is 12 percent.")
        self.arbiter.notify_speech_end()

        # User says completely different command
        user_utterance = "What is the capital of France?"
        result = self.arbiter.differentiate_input(user_utterance)
        self.assertFalse(result["is_system_echo"])
        self.assertEqual(result["source"], "user_voice")
        self.assertEqual(result["clean_text"], user_utterance)

    def test_similarity_ratio_fuzzy_match(self):
        # System says sentence
        self.arbiter.notify_speech_start("Your reminder for dentist appointment is set for 4 PM.")
        self.arbiter.notify_speech_end()

        # STT slightly misrecognizes due to acoustic reverb:
        # e.g., "reminder for dentist appointment set 4 PM"
        muffled = "reminder for dentist appointment set 4 pm"
        result = self.arbiter.differentiate_input(muffled)
        self.assertTrue(result["is_system_echo"])
        self.assertEqual(result["source"], "system_voice")

    def test_wake_word_self_trigger_rejection(self):
        # System says a sentence containing the wake word
        self.arbiter.notify_speech_start("You can activate me anytime by saying Hey MINE.")
        self.arbiter.notify_speech_end()

        # Microphone captures "hey mine" from the speaker
        result = self.arbiter.differentiate_input("hey mine")
        self.assertTrue(result["is_system_echo"])
        self.assertEqual(result["source"], "system_voice")

    def test_during_speech_active_bleed_detection(self):
        # System is actively speaking right now
        self.arbiter.notify_speech_start("Processing your request, please wait a moment.")
        self.assertTrue(self.arbiter.is_system_speaking())

        # Audio captured during active speech
        result = self.arbiter.differentiate_input("please wait a moment")
        self.assertTrue(result["is_system_echo"])

        self.arbiter.notify_speech_end()
        self.assertFalse(self.arbiter.is_system_speaking())

    def test_wait_for_system_voice_cooldown(self):
        # Start speech
        self.arbiter.notify_speech_start("Short speech")
        start = time.time()

        # Spawn a thread to end speech after 0.1s
        import threading
        def end_soon():
            time.sleep(0.1)
            self.arbiter.notify_speech_end()

        threading.Thread(target=end_soon, daemon=True).start()

        # wait_for_system_voice should wait for speech end + cooldown
        quiet = self.arbiter.wait_for_system_voice(timeout=2.0)
        elapsed = time.time() - start

        self.assertTrue(quiet)
        self.assertGreaterEqual(elapsed, 0.1)

    def test_state_listener_notifications(self):
        events = []

        def on_event(event_type, data):
            events.append((event_type, data))

        self.arbiter.register_state_listener(on_event)

        self.arbiter.notify_speech_start("Hello testing")
        self.arbiter.notify_speech_end()
        self.arbiter.notify_listen_start()
        self.arbiter.notify_listen_end()

        event_names = [e[0] for e in events]
        self.assertIn("system_voice_start", event_names)
        self.assertIn("system_voice_end", event_names)
        self.assertIn("mic_listen_start", event_names)
        self.assertIn("mic_listen_end", event_names)


if __name__ == "__main__":
    unittest.main()

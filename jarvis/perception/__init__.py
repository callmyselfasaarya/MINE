import logging
from typing import Any, Dict, Optional
from jarvis.perception.sensors import SensorPerception
from jarvis.perception.vision import VisionPerception
from jarvis.perception.ocr import OCRPerception
from jarvis.perception.stt import STTPerception

logger = logging.getLogger(__name__)

class PerceptionSubsystem:
    """
    Unified Perception Subsystem according to Assistant Architecture:
    - STT: Speech to text and acoustic listening
    - Vision: Camera, screen capture, and visual scene understanding
    - OCR: Text extraction from screen & images
    - Sensors: Real-time hardware and OS environment telemetry
    """

    def __init__(self):
        self.sensors = SensorPerception()
        self.vision = VisionPerception()
        self.ocr = OCRPerception()
        self.stt = STTPerception()

    def get_world_state(self) -> Dict[str, Any]:
        """Snapshot of current world and user state."""
        return {
            "sensors": self.sensors.get_snapshot(),
            "voice": self.stt.get_status()
        }

    def inspect_visual_context(self, prompt: str = "Analyze the current screen state.") -> Dict[str, Any]:
        """Capture screen and analyze visual content."""
        screen = self.vision.capture_screen()
        if not screen.get("success"):
            return screen
        analysis = self.vision.analyze_image(screen["path"], prompt=prompt)
        return {
            "screen": screen,
            "analysis": analysis
        }

# Global singleton
perception = PerceptionSubsystem()

__all__ = ["PerceptionSubsystem", "SensorPerception", "VisionPerception", "OCRPerception", "STTPerception", "perception"]

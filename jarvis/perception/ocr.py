import io
import logging
import os
from pathlib import Path
from typing import Any, Dict, Optional, Union
from PIL import Image
import pyautogui

logger = logging.getLogger(__name__)

class OCRPerception:
    """
    Optical Character Recognition (OCR) Perception Subsystem:
    - Extracts text from screen, regions, or saved image files
    - Uses pytesseract with graceful fallback
    """

    def __init__(self):
        self._tesseract_available = False
        self._init_tesseract()

    def _init_tesseract(self):
        try:
            import pytesseract
            # Check common Windows tesseract install locations if not in PATH
            tesseract_paths = [
                r"C:\Program Files\Tesseract-OCR\tesseract.exe",
                r"C:\Program Files (x86)\Tesseract-OCR\tesseract.exe",
                os.getenv("TESSERACT_CMD", "")
            ]
            for p in tesseract_paths:
                if p and Path(p).exists():
                    pytesseract.pytesseract.tesseract_cmd = p
                    break
            self._tesseract_available = True
        except Exception as e:
            logger.debug(f"Pytesseract not initialized: {e}")
            self._tesseract_available = False

    def extract_text_from_image(self, image_input: Union[str, Path, Image.Image]) -> Dict[str, Any]:
        """Extract text from an image file path or PIL Image object."""
        try:
            if isinstance(image_input, (str, Path)):
                img = Image.open(image_input)
            else:
                img = image_input

            if self._tesseract_available:
                import pytesseract
                text = pytesseract.image_to_string(img)
                return {
                    "success": True,
                    "text": text.strip(),
                    "char_count": len(text.strip()),
                    "engine": "pytesseract"
                }
            else:
                return {
                    "success": False,
                    "text": "",
                    "error": "Tesseract OCR binary not found in standard system paths.",
                    "engine": "none"
                }
        except Exception as e:
            logger.error(f"OCR extraction failed: {e}")
            return {
                "success": False,
                "text": "",
                "error": str(e),
                "engine": "error"
            }

    def read_screen_text(self, region: Optional[tuple] = None) -> Dict[str, Any]:
        """
        Capture the screen (or specific region: x, y, width, height) and extract text.
        """
        try:
            screenshot = pyautogui.screenshot(region=region) if region else pyautogui.screenshot()
            result = self.extract_text_from_image(screenshot)
            result["region"] = region or "full_screen"
            return result
        except Exception as e:
            logger.error(f"Screen OCR failed: {e}")
            return {
                "success": False,
                "text": "",
                "error": str(e)
            }

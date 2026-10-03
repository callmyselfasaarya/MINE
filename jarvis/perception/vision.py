import io
import logging
from datetime import datetime
from pathlib import Path
from typing import Any, Dict, Optional, Union
import cv2
from PIL import Image
import pyautogui

from jarvis.config import DATA_DIR, DOCUMENTS_DIR, GEMINI_API_KEY, GEMINI_MODEL, LLM_PROVIDER

logger = logging.getLogger(__name__)

CAPTURES_DIR = DATA_DIR / "captures"
CAPTURES_DIR.mkdir(parents=True, exist_ok=True)

class VisionPerception:
    """
    Vision Perception Subsystem:
    - Screen capture & window inspection
    - Webcam snapshot capture via OpenCV
    - Multimodal visual reasoning (Gemini Vision / local CV heuristics)
    """

    def capture_screen(self, filename: Optional[str] = None, region: Optional[tuple] = None) -> Dict[str, Any]:
        """Capture display screen or region."""
        try:
            timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
            fname = filename or f"screen_{timestamp}.png"
            if not fname.endswith((".png", ".jpg", ".jpeg")):
                fname += ".png"
            target_path = CAPTURES_DIR / fname

            img = pyautogui.screenshot(region=region) if region else pyautogui.screenshot()
            img.save(str(target_path))

            return {
                "success": True,
                "path": str(target_path),
                "filename": fname,
                "width": img.width,
                "height": img.height,
                "timestamp": timestamp
            }
        except Exception as e:
            logger.error(f"Screen capture failed: {e}")
            return {"success": False, "error": str(e)}

    def capture_camera_frame(self, camera_index: int = 0, filename: Optional[str] = None) -> Dict[str, Any]:
        """Capture a single frame from the connected webcam."""
        cap = None
        try:
            cap = cv2.VideoCapture(camera_index)
            if not cap.isOpened():
                return {
                    "success": False,
                    "error": f"Camera index {camera_index} could not be opened or is not connected."
                }

            # Warm up camera sensor
            for _ in range(3):
                ret, frame = cap.read()

            if not ret or frame is None:
                return {"success": False, "error": "Failed to read video frame from camera."}

            timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
            fname = filename or f"camera_{timestamp}.jpg"
            if not fname.endswith((".jpg", ".png")):
                fname += ".jpg"
            target_path = CAPTURES_DIR / fname

            cv2.imwrite(str(target_path), frame)
            h, w = frame.shape[:2]

            return {
                "success": True,
                "path": str(target_path),
                "filename": fname,
                "width": w,
                "height": h,
                "timestamp": timestamp
            }
        except Exception as e:
            logger.error(f"Camera frame capture failed: {e}")
            return {"success": False, "error": str(e)}
        finally:
            if cap is not None:
                cap.release()

    def analyze_image(self, image_path: Union[str, Path], prompt: str = "Describe what is visible in this image in detail.") -> Dict[str, Any]:
        """
        Analyze an image:
        1. If Gemini API key is configured, uses Gemini 2.5 Flash multimodal vision.
        2. Otherwise, performs local computer vision heuristics (dimensions, brightness, dominant colors, edge count).
        """
        p = Path(image_path)
        if not p.exists():
            return {"success": False, "error": f"Image file not found: {image_path}"}

        # Attempt Gemini Multimodal Vision if key is available
        if GEMINI_API_KEY:
            try:
                from google import genai
                from google.genai import types

                client = genai.Client(api_key=GEMINI_API_KEY)
                with open(p, "rb") as f:
                    img_bytes = f.read()

                mime_type = "image/png" if p.suffix.lower() == ".png" else "image/jpeg"
                response = client.models.generate_content(
                    model=GEMINI_MODEL,
                    contents=[
                        types.Part.from_bytes(data=img_bytes, mime_type=mime_type),
                        prompt
                    ]
                )
                description = response.text or "No visual description generated."
                return {
                    "success": True,
                    "provider": "gemini-vision",
                    "model": GEMINI_MODEL,
                    "description": description,
                    "path": str(p)
                }
            except Exception as e:
                logger.warning(f"Gemini vision call failed ({e}). Falling back to local analysis.")

        # Local Computer Vision heuristic analysis
        try:
            cv_img = cv2.imread(str(p))
            if cv_img is None:
                return {"success": False, "error": "Could not read image file."}

            h, w = cv_img.shape[:2]
            gray = cv2.cvtColor(cv_img, cv2.COLOR_BGR2GRAY)
            mean_brightness = float(gray.mean())
            contrast = float(gray.std())
            edges = cv2.Canny(gray, 100, 200)
            edge_density = float((edges > 0).mean())

            desc = (
                f"Image analysis for '{p.name}': Resolution is {w}x{h} pixels. "
                f"Mean brightness is {mean_brightness:.1f}/255 ({'bright' if mean_brightness > 130 else 'dark/dim'}). "
                f"Visual complexity/detail density is {edge_density * 100:.1f}%."
            )

            return {
                "success": True,
                "provider": "local-cv",
                "description": desc,
                "metadata": {
                    "width": w,
                    "height": h,
                    "mean_brightness": round(mean_brightness, 1),
                    "contrast": round(contrast, 1),
                    "edge_density": round(edge_density, 3)
                },
                "path": str(p)
            }
        except Exception as e:
            return {"success": False, "error": f"Image analysis failed: {e}"}

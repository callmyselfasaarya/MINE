import logging
from typing import Any, Dict, Optional
from jarvis.tools.registry import register_tool
from jarvis.execution import execution
from jarvis.perception import perception

logger = logging.getLogger(__name__)

@register_tool(
    name="press_hotkey",
    description="Simulate pressing a keyboard shortcut combination on Windows (e.g. 'ctrl+c', 'win+d', 'alt+tab', 'ctrl+shift+esc').",
    parameters={
        "hotkey": {"type": "string", "description": "Key combo separated by '+'", "required": True}
    }
)
def press_hotkey(hotkey: str) -> Dict[str, Any]:
    """Press keyboard hotkey combination."""
    return execution.pc.press_keys(hotkey)

@register_tool(
    name="type_text",
    description="Simulate keyboard typing into the active desktop application window.",
    parameters={
        "text": {"type": "string", "description": "Text to type", "required": True}
    }
)
def type_text(text: str) -> Dict[str, Any]:
    """Simulate keyboard typing."""
    return execution.pc.type_text(text)

@register_tool(
    name="mouse_click",
    description="Simulate a mouse click at specific screen coordinates or current cursor location.",
    parameters={
        "x": {"type": "integer", "description": "X coordinate (optional)", "required": False},
        "y": {"type": "integer", "description": "Y coordinate (optional)", "required": False},
        "clicks": {"type": "integer", "description": "Number of clicks (1 for single, 2 for double)", "required": False}
    }
)
def mouse_click(x: Optional[int] = None, y: Optional[int] = None, clicks: int = 1) -> Dict[str, Any]:
    """Simulate mouse click."""
    return execution.pc.mouse_click(x=x, y=y, clicks=clicks)

@register_tool(
    name="get_sensor_snapshot",
    description="Retrieve comprehensive hardware vitals and active window/environment telemetry snapshot.",
    parameters={}
)
def get_sensor_snapshot() -> Dict[str, Any]:
    """Get perception sensor snapshot."""
    return perception.sensors.get_snapshot()

@register_tool(
    name="read_screen_ocr",
    description="Read and extract textual content currently displayed on the computer screen using OCR.",
    parameters={}
)
def read_screen_ocr() -> Dict[str, Any]:
    """Read visible text on display."""
    return perception.ocr.read_screen_text()

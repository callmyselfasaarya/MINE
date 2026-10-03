import logging
from typing import Any, Dict, Optional
from jarvis.tools.registry import register_tool
from jarvis.execution import execution

logger = logging.getLogger(__name__)

@register_tool(
    name="get_weather",
    description="Get current live weather conditions and temperature for any city or current location.",
    parameters={
        "city": {"type": "string", "description": "City name (e.g. 'London', 'New York', 'Mumbai') or leave empty for local area", "required": False}
    }
)
def get_weather(city: str = "") -> Dict[str, Any]:
    """Retrieve weather data."""
    return execution.apps_api.get_weather(city)

@register_tool(
    name="control_smart_home",
    description="Turn on, turn off, dim, or adjust temperature of smart home devices (lights, switches, plugs, thermostat).",
    parameters={
        "device_id": {"type": "string", "description": "Device name or id (e.g. 'living_room_light', 'desk_lamp', 'smart_plug', 'thermostat')", "required": True},
        "state": {"type": "string", "description": "'on' or 'off'", "required": True},
        "brightness": {"type": "integer", "description": "Brightness percentage (0 to 100 for lights)", "required": False},
        "temperature": {"type": "float", "description": "Target temperature in Celsius (for thermostat)", "required": False}
    }
)
def control_smart_home(device_id: str, state: str, brightness: Optional[int] = None, temperature: Optional[float] = None) -> Dict[str, Any]:
    """Control smart home devices."""
    return execution.smart_home.set_device_state(device_id, state, brightness, temperature)

@register_tool(
    name="list_smart_devices",
    description="List all available smart home IoT devices and their current on/off states.",
    parameters={}
)
def list_smart_devices() -> Dict[str, Any]:
    """List smart home devices."""
    return execution.smart_home.list_devices()

@register_tool(
    name="trigger_smart_scene",
    description="Trigger a smart home scene preset such as 'night', 'work', 'movie', or 'focus'.",
    parameters={
        "scene_name": {"type": "string", "description": "Name of the scene (e.g. 'night', 'work', 'movie')", "required": True}
    }
)
def trigger_smart_scene(scene_name: str) -> Dict[str, Any]:
    """Trigger smart home preset scene."""
    return execution.smart_home.trigger_scene(scene_name)

@register_tool(
    name="call_api_webhook",
    description="Send a REST or Webhook request to an external API endpoint.",
    parameters={
        "url": {"type": "string", "description": "Webhook endpoint URL", "required": True},
        "method": {"type": "string", "description": "HTTP method (POST, GET, PUT)", "required": False},
        "payload": {"type": "object", "description": "JSON payload dictionary", "required": False}
    },
    requires_confirmation=True,
    dangerous=False
)
def call_api_webhook(url: str, method: str = "POST", payload: Optional[Dict[str, Any]] = None) -> Dict[str, Any]:
    """Send webhook request."""
    return execution.apps_api.call_webhook(url, method, payload)

import json
import logging
import os
from pathlib import Path
from typing import Any, Dict, List, Optional
import requests

from jarvis.config import DATA_DIR

logger = logging.getLogger(__name__)

SMART_HOME_FILE = DATA_DIR / "smart_home.json"

DEFAULT_DEVICES = {
    "living_room_light": {
        "name": "Living Room Light",
        "type": "light",
        "state": "off",
        "brightness": 100,
        "color": "warm_white"
    },
    "desk_lamp": {
        "name": "Desk Lamp",
        "type": "light",
        "state": "on",
        "brightness": 80,
        "color": "daylight"
    },
    "smart_plug": {
        "name": "Main Desk Power Plug",
        "type": "switch",
        "state": "on",
        "power_watts": 45
    },
    "thermostat": {
        "name": "Room Thermostat",
        "type": "climate",
        "state": "on",
        "target_temp_c": 22.0,
        "mode": "auto"
    }
}

class SmartHomeExecutor:
    """
    Smart Home Action Execution:
    - Controls IoT smart devices (lights, switches, climate)
    - Supports local virtual smart devices with persistence
    - Connects to Home Assistant instance if HASS_URL is defined
    """

    def __init__(self):
        self.hass_url = os.getenv("HASS_URL", "").rstrip("/")
        self.hass_token = os.getenv("HASS_TOKEN", "")
        self.devices = self._load_devices()

    def _load_devices(self) -> Dict[str, Any]:
        if not SMART_HOME_FILE.exists():
            self._save_devices(DEFAULT_DEVICES)
            return dict(DEFAULT_DEVICES)
        try:
            with open(SMART_HOME_FILE, "r", encoding="utf-8") as f:
                return json.load(f)
        except Exception as e:
            logger.error(f"Failed to load smart home state: {e}")
            return dict(DEFAULT_DEVICES)

    def _save_devices(self, data: Dict[str, Any]):
        try:
            SMART_HOME_FILE.parent.mkdir(parents=True, exist_ok=True)
            with open(SMART_HOME_FILE, "w", encoding="utf-8") as f:
                json.dump(data, f, indent=2)
        except Exception as e:
            logger.error(f"Failed to save smart home state: {e}")

    def list_devices(self) -> Dict[str, Any]:
        """List all managed smart home devices and current states."""
        return {
            "success": True,
            "devices": self.devices,
            "count": len(self.devices)
        }

    def set_device_state(self, device_id: str, state: str, brightness: Optional[int] = None, temperature: Optional[float] = None) -> Dict[str, Any]:
        """Set on/off state, brightness, or temperature for a smart device."""
        clean_id = device_id.strip().lower().replace(" ", "_")

        # Check Home Assistant integration first if configured
        if self.hass_url and self.hass_token:
            try:
                domain = "light" if "light" in clean_id or "lamp" in clean_id else "switch"
                service = "turn_on" if state.lower() == "on" else "turn_off"
                url = f"{self.hass_url}/api/services/{domain}/{service}"
                headers = {"Authorization": f"Bearer {self.hass_token}", "Content-Type": "application/json"}
                payload = {"entity_id": f"{domain}.{clean_id}"}
                if brightness is not None and state.lower() == "on":
                    payload["brightness_pct"] = brightness
                resp = requests.post(url, headers=headers, json=payload, timeout=4)
                if resp.status_code == 200:
                    return {"success": True, "message": f"Updated {clean_id} via Home Assistant to {state}."}
            except Exception as e:
                logger.warning(f"Home Assistant call failed: {e}. Falling back to local state.")

        # Local virtual device handling
        if clean_id not in self.devices:
            # Check for partial name match
            matched = None
            for k, v in self.devices.items():
                if clean_id in k or clean_id in v["name"].lower():
                    matched = k
                    break
            if matched:
                clean_id = matched
            else:
                return {"success": False, "error": f"Device '{device_id}' not found."}

        dev = self.devices[clean_id]
        dev["state"] = state.lower()
        if brightness is not None and dev["type"] == "light":
            dev["brightness"] = max(0, min(100, int(brightness)))
        if temperature is not None and dev["type"] == "climate":
            dev["target_temp_c"] = float(temperature)

        self._save_devices(self.devices)
        return {
            "success": True,
            "device": dev["name"],
            "state": dev["state"],
            "message": f"{dev['name']} is now turned {dev['state']}."
        }

    def toggle_device(self, device_id: str) -> Dict[str, Any]:
        """Toggle a smart device between ON and OFF."""
        clean_id = device_id.strip().lower().replace(" ", "_")
        matched = None
        for k, v in self.devices.items():
            if clean_id == k or clean_id in k or clean_id in v["name"].lower():
                matched = k
                break
        if not matched:
            return {"success": False, "error": f"Device '{device_id}' not found."}

        current = self.devices[matched].get("state", "off")
        new_state = "off" if current == "on" else "on"
        return self.set_device_state(matched, new_state)

    def trigger_scene(self, scene_name: str) -> Dict[str, Any]:
        """Trigger smart home presets (e.g., 'night', 'work', 'movie')."""
        s = scene_name.strip().lower()
        if "night" in s or "sleep" in s:
            for k, v in self.devices.items():
                if v["type"] == "light":
                    v["state"] = "off"
            self._save_devices(self.devices)
            return {"success": True, "message": "Night scene activated: all lights turned off."}

        elif "work" in s or "focus" in s:
            if "desk_lamp" in self.devices:
                self.devices["desk_lamp"]["state"] = "on"
                self.devices["desk_lamp"]["brightness"] = 100
            self._save_devices(self.devices)
            return {"success": True, "message": "Focus scene activated: desk lamp set to 100%."}

        elif "movie" in s or "cinema" in s:
            if "living_room_light" in self.devices:
                self.devices["living_room_light"]["state"] = "on"
                self.devices["living_room_light"]["brightness"] = 20
            self._save_devices(self.devices)
            return {"success": True, "message": "Cinema scene activated: dimmed living room lights to 20%."}

        return {"success": False, "error": f"Unknown scene preset: {scene_name}"}

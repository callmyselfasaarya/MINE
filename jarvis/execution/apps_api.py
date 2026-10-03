import logging
import urllib.parse
from typing import Any, Dict, Optional
import requests

logger = logging.getLogger(__name__)

class AppsAPIExecutor:
    """
    Apps & APIs Execution Subsystem:
    - Weather API queries (using free open-meteo / wttr.in with zero API key required)
    - Webhook and REST API dispatch
    - External service integration
    """

    def get_weather(self, city: str = "auto") -> Dict[str, Any]:
        """
        Fetch real-time weather information for any city or current IP location.
        Uses wttr.in JSON API.
        """
        target_city = city.strip() if city and city != "auto" else ""
        url = f"https://wttr.in/{urllib.parse.quote(target_city)}?format=j1"

        try:
            resp = requests.get(url, timeout=6)
            resp.raise_for_status()
            data = resp.json()

            current = data["current_condition"][0]
            temp_c = current.get("temp_C")
            temp_f = current.get("temp_F")
            desc = current.get("weatherDesc", [{}])[0].get("value", "Clear")
            humidity = current.get("humidity")
            wind_kmph = current.get("windspeedKmph")

            area_info = data.get("nearest_area", [{}])[0]
            area_name = area_info.get("areaName", [{}])[0].get("value", city or "Local Area")
            country = area_info.get("country", [{}])[0].get("value", "")

            summary = f"Weather in {area_name}, {country}: {desc}, {temp_c}°C ({temp_f}°F), humidity {humidity}%, wind {wind_kmph} km/h."

            return {
                "success": True,
                "city": area_name,
                "country": country,
                "temp_c": temp_c,
                "temp_f": temp_f,
                "description": desc,
                "humidity": humidity,
                "wind_kmph": wind_kmph,
                "summary": summary
            }
        except Exception as e:
            logger.error(f"Weather query failed: {e}")
            return {
                "success": False,
                "error": f"Failed to retrieve weather for '{city}': {str(e)}"
            }

    def call_webhook(self, url: str, method: str = "POST", payload: Optional[Dict[str, Any]] = None) -> Dict[str, Any]:
        """Send HTTP webhook or REST request."""
        try:
            m = method.upper().strip()
            if m == "POST":
                resp = requests.post(url, json=payload or {}, timeout=10)
            elif m == "GET":
                resp = requests.get(url, params=payload or {}, timeout=10)
            else:
                resp = requests.request(m, url, json=payload or {}, timeout=10)

            return {
                "success": 200 <= resp.status_code < 300,
                "status_code": resp.status_code,
                "response_text": resp.text[:1000]
            }
        except Exception as e:
            return {"success": False, "error": str(e)}

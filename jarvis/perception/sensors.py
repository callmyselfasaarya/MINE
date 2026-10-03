import ctypes
import logging
import platform
import psutil
import pyautogui
from datetime import datetime
from typing import Any, Dict, List, Optional

logger = logging.getLogger(__name__)

def get_active_window_title() -> str:
    """Retrieve the title of the active foreground window on Windows OS."""
    if platform.system() != "Windows":
        return "Unknown"
    try:
        user32 = ctypes.windll.user32
        h_wnd = user32.GetForegroundWindow()
        length = user32.GetWindowTextLengthW(h_wnd)
        if length > 0:
            buff = ctypes.create_unicode_buffer(length + 1)
            user32.GetWindowTextW(h_wnd, buff, length + 1)
            return buff.value
        return "Desktop / Background"
    except Exception as e:
        logger.debug(f"Failed to get active window title: {e}")
        return "Unknown"

def get_clipboard_text(max_length: int = 250) -> Optional[str]:
    """Safely inspect current clipboard content if text."""
    try:
        if platform.system() == "Windows":
            user32 = ctypes.windll.user32
            kernel32 = ctypes.windll.kernel32
            if not user32.OpenClipboard(None):
                return None
            try:
                CF_UNICODETEXT = 13
                h_clip = user32.GetClipboardData(CF_UNICODETEXT)
                if not h_clip:
                    return None
                p_text = kernel32.GlobalLock(h_clip)
                if not p_text:
                    return None
                try:
                    text = ctypes.c_wchar_p(p_text).value
                    if text:
                        cleaned = text.strip()
                        return cleaned[:max_length] + ("..." if len(cleaned) > max_length else "")
                    return None
                finally:
                    kernel32.GlobalUnlock(h_clip)
            finally:
                user32.CloseClipboard()
    except Exception as e:
        logger.debug(f"Clipboard read error: {e}")
    return None

class SensorPerception:
    """
    Sensors subsystem:
    - Hardware vitals (CPU, RAM, Battery, Disk)
    - OS & Environment vitals (Active window, screen resolution, clipboard, running apps)
    """

    def get_hardware_telemetry(self) -> Dict[str, Any]:
        cpu_percent = psutil.cpu_percent(interval=None)
        cpu_count = psutil.cpu_count(logical=True)
        ram = psutil.virtual_memory()
        disk = psutil.disk_usage("/")

        battery = psutil.sensors_battery()
        battery_data = None
        if battery:
            battery_data = {
                "percent": battery.percent,
                "power_plugged": battery.power_plugged,
                "seconds_left": battery.secsleft if battery.secsleft != psutil.POWER_TIME_UNLIMITED else None
            }

        return {
            "cpu": {
                "percent": cpu_percent,
                "cores": cpu_count
            },
            "ram": {
                "percent": ram.percent,
                "used_gb": round(ram.used / (1024 ** 3), 1),
                "total_gb": round(ram.total / (1024 ** 3), 1)
            },
            "disk": {
                "percent": disk.percent,
                "free_gb": round(disk.free / (1024 ** 3), 1),
                "total_gb": round(disk.total / (1024 ** 3), 1)
            },
            "battery": battery_data
        }

    def get_environment_telemetry(self) -> Dict[str, Any]:
        screen_w, screen_h = pyautogui.size()
        active_window = get_active_window_title()
        clipboard_snippet = get_clipboard_text()

        # Check top running apps by CPU/Memory
        top_apps = []
        try:
            for p in sorted(psutil.process_iter(['name', 'cpu_percent', 'memory_percent']),
                            key=lambda p: p.info.get('memory_percent') or 0,
                            reverse=True)[:6]:
                name = p.info.get('name')
                if name and name not in top_apps and not name.lower().startswith("system"):
                    top_apps.append(name)
        except Exception:
            pass

        return {
            "active_window": active_window,
            "screen_resolution": f"{screen_w}x{screen_h}",
            "clipboard_preview": clipboard_snippet,
            "top_apps": top_apps,
            "os": f"{platform.system()} {platform.release()}",
            "current_time": datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        }

    def get_snapshot(self) -> Dict[str, Any]:
        """Consolidated sensor snapshot."""
        hw = self.get_hardware_telemetry()
        env = self.get_environment_telemetry()
        return {
            "hardware": hw,
            "environment": env,
            "timestamp": datetime.now().isoformat()
        }

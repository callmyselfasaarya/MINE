import os
import subprocess
import logging
import platform
import pyautogui
import psutil
from typing import Any, Dict, List, Optional
# Common app shortcuts for Windows
KNOWN_APPS = {
    # System utilities
    "calculator": "calc.exe",
    "calc": "calc.exe",
    "notepad": "notepad.exe",
    "paint": "mspaint.exe",
    "terminal": "powershell.exe",
    "powershell": "powershell.exe",
    "cmd": "cmd.exe",
    "command prompt": "cmd.exe",
    "explorer": "explorer.exe",
    "file explorer": "explorer.exe",
    "task manager": "taskmgr.exe",
    "taskmgr": "taskmgr.exe",
    "control panel": "control.exe",
    "settings": "ms-settings:",
    "snipping tool": "snippingtool.exe",
    "wordpad": "write.exe",
    "clock": "ms-clock:",
    "calendar": "outlookcal:",
    # Browsers
    "browser": "https://www.google.com",
    "chrome": "chrome",
    "google chrome": "chrome",
    "edge": "msedge",
    "microsoft edge": "msedge",
    "firefox": "firefox",
    "opera": "opera",
    "brave": "brave",
    # Dev tools
    "vscode": "code",
    "code": "code",
    "visual studio code": "code",
    "notepad++": "notepad++",
    "git bash": "git-bash",
    # Media
    "vlc": "vlc",
    "vlc media player": "vlc",
    "winamp": "winamp",
    "windows media player": "wmplayer.exe",
    "media player": "wmplayer.exe",
    "groove music": "mswindowsmusic:",
    # Communication
    "discord": "discord",
    "telegram": "telegram",
    "whatsapp": "whatsapp",
    "skype": "skype",
    "zoom": "zoom",
    "teams": "teams",
    "microsoft teams": "teams",
    "slack": "slack",
    # Productivity (Microsoft Office)
    "word": "winword.exe",
    "microsoft word": "winword.exe",
    "excel": "excel.exe",
    "microsoft excel": "excel.exe",
    "powerpoint": "powerpnt.exe",
    "microsoft powerpoint": "powerpnt.exe",
    "outlook": "outlook.exe",
    "microsoft outlook": "outlook.exe",
    # Gaming & streaming
    "steam": "steam",
    "obs": "obs64.exe",
    "obs studio": "obs64.exe",
    "spotify": "spotify",
}

logger = logging.getLogger(__name__)

class PCExecutor:
    """
    PC & OS Action Execution:
    - Launching and managing applications
    - GUI interaction (keyboard, mouse, hotkeys)
    - System audio / media control
    """

    def launch_application(self, app_name: str) -> Dict[str, Any]:
        """Launch desktop software or utility."""
        clean = app_name.strip().lower()
        target = KNOWN_APPS.get(clean, app_name)

        try:
            if target.startswith("http://") or target.startswith("https://"):
                import webbrowser
                webbrowser.open(target)
                return {"success": True, "message": f"Opened {app_name} in web browser."}

            if platform.system() == "Windows":
                if target.endswith(":") or target.startswith("ms-"):
                    os.system(f"start {target}")
                else:
                    subprocess.Popen(target, shell=True)
            else:
                subprocess.Popen([target])

            return {"success": True, "message": f"Launched {app_name}."}
        except Exception as e:
            logger.error(f"Failed to launch {app_name}: {e}")
            return {"success": False, "error": str(e)}

    def press_keys(self, hotkey_str: str) -> Dict[str, Any]:
        """
        Press a hotkey combination (e.g., 'ctrl+c', 'alt+tab', 'win+d', 'volumeup').
        """
        try:
            keys = [k.strip().lower() for k in hotkey_str.split("+")]
            pyautogui.hotkey(*keys)
            return {"success": True, "message": f"Pressed hotkey combo: {' + '.join(keys)}"}
        except Exception as e:
            return {"success": False, "error": str(e)}

    def type_text(self, text: str, interval: float = 0.02) -> Dict[str, Any]:
        """Simulate typing text into the currently active window."""
        try:
            pyautogui.write(text, interval=interval)
            return {"success": True, "message": f"Typed {len(text)} characters."}
        except Exception as e:
            return {"success": False, "error": str(e)}

    def mouse_click(self, x: Optional[int] = None, y: Optional[int] = None, clicks: int = 1) -> Dict[str, Any]:
        """Click mouse at coordinates or current position."""
        try:
            if x is not None and y is not None:
                pyautogui.click(x=x, y=y, clicks=clicks)
            else:
                pyautogui.click(clicks=clicks)
            return {"success": True, "message": f"Clicked mouse {clicks} time(s)."}
        except Exception as e:
            return {"success": False, "error": str(e)}

    def media_control(self, action: str) -> Dict[str, Any]:
        """Control system volume and media playback."""
        act = action.strip().lower()
        key_map = {
            "play_pause": "playpause",
            "next": "nexttrack",
            "previous": "prevtrack",
            "volume_up": "volumeup",
            "volume_down": "volumedown",
            "mute": "volumemute"
        }
        if act in key_map:
            pyautogui.press(key_map[act])
            return {"success": True, "message": f"Executed media command: {act}"}
        return {"success": False, "error": f"Unknown media action: {action}"}

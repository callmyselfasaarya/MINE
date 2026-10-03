import os
import platform
import subprocess
import logging
from datetime import datetime
from pathlib import Path
from typing import Any, Dict
import psutil
import pyautogui

from jarvis.config import DATA_DIR
from jarvis.tools.registry import register_tool

logger = logging.getLogger(__name__)

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


@register_tool(
    name="get_system_status",
    description="Check real-time computer hardware status including CPU usage, RAM memory, battery level, and disk space.",
    parameters={}
)
def get_system_status() -> Dict[str, Any]:
    """Retrieve system telemetry and hardware metrics."""
    cpu_percent = psutil.cpu_percent(interval=0.3)
    cpu_count = psutil.cpu_count(logical=True)

    ram = psutil.virtual_memory()
    disk = psutil.disk_usage("/")

    battery = psutil.sensors_battery()
    battery_info = None
    if battery:
        battery_info = {
            "percent": round(battery.percent, 1),
            "power_plugged": battery.power_plugged,
            "secs_left": battery.secsleft if battery.secsleft != psutil.POWER_TIME_UNLIMITED else "Plugged In"
        }

    return {
        "os": f"{platform.system()} {platform.release()}",
        "cpu_usage_percent": cpu_percent,
        "cpu_cores": cpu_count,
        "ram_usage_percent": ram.percent,
        "ram_used_gb": round(ram.used / (1024 ** 3), 2),
        "ram_total_gb": round(ram.total / (1024 ** 3), 2),
        "disk_free_gb": round(disk.free / (1024 ** 3), 2),
        "disk_total_gb": round(disk.total / (1024 ** 3), 2),
        "battery": battery_info,
        "status_summary": f"CPU at {cpu_percent}%, Memory at {ram.percent}% ({round(ram.used / (1024 ** 3), 1)}GB of {round(ram.total / (1024 ** 3), 1)}GB used)."
    }


@register_tool(
    name="open_application",
    description="Launch an application or open a file/url on the computer (e.g. calculator, notepad, explorer, browser).",
    parameters={
        "app_name": {"type": "string", "description": "The name of the app to launch (e.g., 'calculator', 'notepad', 'explorer', 'browser')", "required": True}
    }
)
def open_application(app_name: str) -> Dict[str, Any]:
    """Launch local application."""
    clean_name = app_name.lower().strip()
    target = KNOWN_APPS.get(clean_name, app_name)

    try:
        if target.startswith("http://") or target.startswith("https://"):
            import webbrowser
            webbrowser.open(target)
            return {"success": True, "message": f"Opened browser to {target}."}
        else:
            # Launch detached process on Windows
            subprocess.Popen(target, shell=True)
            return {"success": True, "message": f"Successfully launched {app_name}."}
    except Exception as e:
        logger.error(f"Error launching app '{app_name}': {e}")
        return {"success": False, "error": f"Failed to open '{app_name}': {str(e)}"}


@register_tool(
    name="take_screenshot",
    description="Capture a screenshot of the computer screen and save it locally.",
    parameters={
        "filename": {"type": "string", "description": "Optional name for the screenshot image file", "required": False}
    }
)
def take_screenshot(filename: str = "") -> Dict[str, Any]:
    """Capture screen screenshot."""
    try:
        screenshots_dir = DATA_DIR / "screenshots"
        screenshots_dir.mkdir(parents=True, exist_ok=True)

        if not filename:
            filename = f"screenshot_{datetime.now().strftime('%Y%m%d_%H%M%S')}.png"
        elif not filename.endswith(".png"):
            filename += ".png"

        save_path = screenshots_dir / filename
        screenshot = pyautogui.screenshot()
        screenshot.save(save_path)

        return {
            "success": True,
            "filename": filename,
            "path": str(save_path),
            "message": f"Screenshot saved to {save_path.name}."
        }
    except Exception as e:
        return {"success": False, "error": f"Failed to take screenshot: {str(e)}"}


@register_tool(
    name="control_media",
    description="Control PC volume or media playback keys (playpause, next, prev, mute, volumeup, volumedown).",
    parameters={
        "action": {"type": "string", "description": "Action: 'playpause', 'next', 'prev', 'mute', 'volumeup', 'volumedown'", "required": True}
    }
)
def control_media(action: str) -> Dict[str, Any]:
    """Simulate multimedia keyboard actions."""
    action = action.lower().replace("_", "").replace("-", "").replace(" ", "")
    action_map = {
        "playpause": "playpause",
        "play": "playpause",
        "pause": "playpause",
        "next": "nexttrack",
        "nexttrack": "nexttrack",
        "prev": "prevtrack",
        "prevtrack": "prevtrack",
        "mute": "volumemute",
        "volumeup": "volumeup",
        "volumedown": "volumedown"
    }

    key = action_map.get(action)
    if not key:
        return {"success": False, "error": f"Unknown media action '{action}'. Options: playpause, next, prev, mute, volumeup, volumedown."}

    try:
        pyautogui.press(key)
        return {"success": True, "message": f"Executed media control: {action}."}
    except Exception as e:
        return {"success": False, "error": f"Could not trigger media key: {str(e)}"}


@register_tool(
    name="run_system_command",
    description="Execute a terminal command on the computer. (DANGEROUS ACTION: Requires user authorization).",
    parameters={
        "command": {"type": "string", "description": "The command line string to execute", "required": True}
    },
    requires_confirmation=True,
    dangerous=True
)
def run_system_command(command: str) -> Dict[str, Any]:
    """Execute shell command after confirmation."""
    try:
        res = subprocess.run(command, shell=True, capture_output=True, text=True, timeout=15)
        output = res.stdout if res.returncode == 0 else (res.stderr or res.stdout)
        return {
            "success": res.returncode == 0,
            "returncode": res.returncode,
            "output": output.strip() if output else "(No output returned)"
        }
    except subprocess.TimeoutExpired:
        return {"success": False, "error": "Command timed out after 15 seconds."}
    except Exception as e:
        return {"success": False, "error": str(e)}


@register_tool(
    name="system_power",
    description="Lock, sleep, shutdown, or restart the computer. (DANGEROUS ACTION: Requires user authorization).",
    parameters={
        "action": {"type": "string", "description": "Power action: 'lock', 'sleep', 'shutdown', or 'restart'", "required": True}
    },
    requires_confirmation=True,
    dangerous=True
)
def system_power(action: str) -> Dict[str, Any]:
    """Execute system power operations."""
    action = action.lower().strip()
    if action == "lock":
        # Windows lock workstation
        subprocess.run("rundll32.exe user32.dll,LockWorkStation", shell=True)
        return {"success": True, "message": "Workstation locked, Sir."}
    elif action == "shutdown":
        subprocess.run("shutdown /s /t 60 /c \"MINE initiated system shutdown\"", shell=True)
        return {"success": True, "message": "Shutdown initiated in 60 seconds. You may run 'shutdown /a' to abort."}
    elif action == "restart":
        subprocess.run("shutdown /r /t 60 /c \"MINE initiated system restart\"", shell=True)
        return {"success": True, "message": "Restart initiated in 60 seconds."}
    elif action == "sleep":
        subprocess.run("rundll32.exe powrprof.dll,SetSuspendState 0,1,0", shell=True)
        return {"success": True, "message": "Putting system to sleep."}
    else:
        return {"success": False, "error": f"Invalid power action '{action}'. Choose from lock, sleep, shutdown, restart."}


@register_tool(
    name="list_capabilities",
    description="List or explain the capabilities and skills of the assistant in natural language.",
    parameters={
        "category": {"type": "string", "description": "Optional category filter like 'general', 'voice', 'vision', 'tools'", "required": False}
    }
)
def list_capabilities(category: str = "general") -> Dict[str, Any]:
    """Provide a comprehensive explanation of assistant capabilities in natural language."""
    from jarvis.config import ASSISTANT_NAME, USER_NAME
    msg = (
        f"I am {ASSISTANT_NAME}, your personal desktop AI assistant, {USER_NAME}. "
        f"My key capabilities include: "
        f"1. Voice Interaction: hands-free voice conversations with active acoustic echo prevention. "
        f"2. Perception: inspecting your screen or camera, visual scene understanding, and OCR text extraction. "
        f"3. Computer & OS Control: monitoring CPU, memory, and battery vitals, launching desktop apps, simulating hotkeys, and managing files. "
        f"4. Knowledge & Search: searching live internet via DuckDuckGo, Google, and Wikipedia. "
        f"5. Productivity: setting natural language reminders and scheduling calendar appointments. "
        f"6. Smart Home: controlling lighting, switches, climate thermostats, and scene presets. "
        f"7. Specialized Sub-Agents: conducting comprehensive multi-source research briefs, writing and safely testing Python code in an isolated sandbox, and orchestrating multi-step execution plans."
    )
    return {
        "success": True,
        "message": msg,
        "confirmation": msg,
        "category": category
    }
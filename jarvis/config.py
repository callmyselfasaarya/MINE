import os
from pathlib import Path
from dotenv import load_dotenv

# Load environment variables
load_dotenv()

BASE_DIR = Path(__file__).resolve().parent.parent
DATA_DIR = BASE_DIR / "data"
DOCUMENTS_DIR = DATA_DIR / "documents"

# Ensure directories exist
DATA_DIR.mkdir(parents=True, exist_ok=True)
DOCUMENTS_DIR.mkdir(parents=True, exist_ok=True)

# File paths
REMINDERS_FILE = DATA_DIR / "reminders.json"
CALENDAR_FILE = DATA_DIR / "calendar.json"
MEMORY_FILE = DATA_DIR / "memory.json"

# Core Settings
ASSISTANT_NAME = os.getenv("ASSISTANT_NAME", "MINE")
USER_NAME = os.getenv("USER_NAME", "Sir")

# AI / LLM Configuration
LLM_PROVIDER = os.getenv("LLM_PROVIDER", "ollama").lower()  # "ollama", "gemini", "local"
OLLAMA_HOST = os.getenv("OLLAMA_HOST", "http://localhost:11434").rstrip("/")
OLLAMA_URL = os.getenv("OLLAMA_URL", f"{OLLAMA_HOST}/api/chat")
OLLAMA_MODEL = os.getenv("OLLAMA_MODEL", "llama3.2")
OLLAMA_TIMEOUT = int(os.getenv("OLLAMA_TIMEOUT", "25"))

GEMINI_API_KEY = os.getenv("GEMINI_API_KEY", os.getenv("GOOGLE_API_KEY", "")).strip()
GEMINI_MODEL = os.getenv("GEMINI_MODEL", "gemini-2.5-flash")

# Voice & Input Configuration
PRIMARY_INPUT_MODE = os.getenv("PRIMARY_INPUT_MODE", "mic").lower().strip()
TTS_ENABLED = os.getenv("TTS_ENABLED", "true").lower() in ("true", "1", "yes")
TTS_RATE = int(os.getenv("TTS_RATE", "190"))
TTS_VOLUME = float(os.getenv("TTS_VOLUME", "1.0"))
MIC_DEVICE_INDEX = int(os.getenv("MIC_DEVICE_INDEX", "-1"))
STT_ENERGY_THRESHOLD = int(os.getenv("STT_ENERGY_THRESHOLD", "180"))
STT_PAUSE_THRESHOLD = float(os.getenv("STT_PAUSE_THRESHOLD", "0.8"))
STT_DYNAMIC_ENERGY = os.getenv("STT_DYNAMIC_ENERGY", "true").lower() in ("true", "1", "yes")

# Wake Word Configuration
WAKE_WORD = os.getenv("WAKE_WORD", "hey mine").lower().strip()
WAKE_WORD_ENABLED = os.getenv("WAKE_WORD_ENABLED", "false").lower() in ("true", "1", "yes")
# Extra wake phrases accepted in addition to WAKE_WORD (comma-separated)
_extra = os.getenv("WAKE_WORD_ALIASES", "")
WAKE_WORD_ALIASES: list = [w.strip().lower() for w in _extra.split(",") if w.strip()]

# Web / Server Configuration
HOST = os.getenv("HOST", "127.0.0.1")
PORT = int(os.getenv("PORT", "8000"))
DEBUG = os.getenv("DEBUG", "false").lower() in ("true", "1", "yes")

# Base System Prompt
SYSTEM_PROMPT = f"""You are {ASSISTANT_NAME}, an advanced, highly intelligent personal AI assistant.
You address the user courteously as '{USER_NAME}'.

Key Guidelines:
1. Tone: Calm, sophisticated, polite, witty when appropriate, highly competent, and concise. Avoid robotic verbosity.
2. Tool Usage: Always use appropriate available tools to fulfill requests (setting reminders, checking calendar, searching the web, reading/creating files, system metrics, remembering details).
3. Dangerous Actions: NEVER run destructive operations (like deleting files, rebooting the PC, or executing shell scripts) without explicit confirmation. If a tool flags dangerous or confirmation required, explain what will happen and request confirmation.
4. Execution Transparency: Clearly state what actions were performed (e.g., "Done, Sir. I've set a reminder for tomorrow at 8:00 AM.").
5. Current Environment: Windows OS. Always format dates, times, and paths appropriately.
"""
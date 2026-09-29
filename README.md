# M.I.N.E. Version 1 MVP

> **M.I.N.E.** — A real, functional personal desktop AI assistant built with modern voice recognition, function-calling tools, conversation context, hardware telemetry, and two-step safety guardrails.

---

## ⚡ The Version 1 Philosophy

**No holograms. No robotics. No facial recognition gimmickry. Just an authentic, responsive assistant that genuinely helps you.**

```
Speech / Web Audio
       ↓
Speech-to-Text (STT)
       ↓
LLM / Intent Parser (Gemini 2.5 Flash / Local Engine)
       ↓
Recognizes: create_reminder()
       ↓
Reminder Daemon / Service
       ↓
Safety & Confirmation Check
       ↓
Text-to-Speech (TTS)
       ↓
"Done. I've set a reminder for tomorrow at 8:00 AM."
```

---

## ✨ Core Capabilities (MVP Checklist)

| Icon | Capability | Implementation Details |
| :--- | :--- | :--- |
| 🎙️ | **Listen to you** | Dual input: Browser Web Speech Recognition & Host PyAudio / `speech_recognition` |
| 🗣️ | **Talk back** | Browser Web Speech Synthesis & Windows SAPI5 (`pyttsx3`/COM) with voice visualizer |
| 🧠 | **Natural Language** | Gemini 2.5 Flash via `google-genai` SDK + Local Intent Parser for offline fallback |
| 💬 | **Conversation Context** | Multi-turn conversation sliding buffer preserving user context and tool exchanges |
| 🧰 | **Tool Calling** | Decorator-based Tool Registry with automatic function declarations & JSON schemas |
| 🔎 | **Search the web** | Real-time web queries via DuckDuckGo and encyclopedic summaries via Wikipedia |
| 📁 | **Read your files** | Secure file content inspection and directory exploration |
| 📝 | **Create/edit docs** | Markdown/text document generation and content appending in `data/documents/` |
| ⏰ | **Set reminders** | Natural language time parser (`parse_natural_time`) + background daemon thread |
| 📅 | **Manage calendar** | Schedule appointments, list daily agendas, and manage upcoming events |
| 🧠 | **Remember facts** | Persistent long-term memory injected directly into the LLM system prompt |
| 🖥️ | **Computer actions** | Hardware vitals (CPU, RAM, Battery via `psutil`), app launcher, screenshots, media keys |
| 🔐 | **Safety guardrails** | Intercepts dangerous actions (file deletion, system shutdown, commands) for user confirmation |

---

## 🚀 Quick Start

### 1. Requirements
Ensure Python 3.10+ is installed. Dependencies are listed in `requirements.txt`:
```bash
pip install -r requirements.txt
```

### 2. Configure LLM Provider (Ollama or Gemini)

**Option 1: Ollama Local LLM (Default & Recommended for 100% Privacy)**
MINE natively integrates with [Ollama](https://ollama.com/) for entirely local, private, and offline-capable intelligence:
```bash
# Pull and start the default Llama 3.2 model
ollama run llama3.2
```
In your `.env`:
```env
LLM_PROVIDER=ollama
OLLAMA_URL=http://localhost:11434/api/chat
OLLAMA_MODEL=llama3.2
```
MINE communicates via:
$$\text{User} \longrightarrow \text{Python Assistant} \longrightarrow \text{Ollama} \longrightarrow \text{Local LLM} \longrightarrow \text{Assistant} \longrightarrow \text{User}$$

**Option 2: Google Gemini (Cloud Reasoning)**
Add your free Gemini API key from [Google AI Studio](https://aistudio.google.com/app/apikey) in `.env`:
```env
LLM_PROVIDER=gemini
GEMINI_API_KEY=your_gemini_api_key_here
GEMINI_MODEL=gemini-2.5-flash
```

> *Note: If Ollama or Gemini are offline or unconfigured, MINE automatically falls back to its built-in rule-based Local Intent Engine with zero downtime.*

---

## 🖥️ Running M.I.N.E.

### Option A: Futuristic Web HUD (Recommended)
Launches the holographic sci-fi dashboard in your browser:
```bash
python main.py
```
- Opens automatically at: `http://127.0.0.1:8000`
- Click the **Arc Reactor Core** or microphone icon to talk directly.
- Real-time audio waveform visualizer and live telemetry panels.

### Option B: Interactive Terminal CLI
Run MINE purely from the command line with colored rich formatting:
```bash
python main.py --cli
```
- Type your commands or type `/mic` to activate microphone voice input.
- Displays tool execution traces and confirmation dialogs.

---

## 🧪 Testing

Run the automated test suite to verify all core capabilities and guardrails:
```bash
python -m unittest tests/test_jarvis_mvp.py
```

---

## 📂 Project Architecture

```
M.I.N.E/
├── main.py                     # Entry point (Web HUD & CLI launcher)
├── requirements.txt            # Python dependencies
├── .env                        # Environment settings (ASSISTANT_NAME=MINE)
├── .env.example                # Environment template
├── mine/                       # Package namespace
│   ├── __init__.py             # M.I.N.E package export
│   └── cli.py                  # CLI launcher alias
├── jarvis/                     # Core system modules
│   ├── config.py               # Settings, paths, and system prompts
│   ├── cli.py                  # Rich terminal CLI interface
│   ├── core/
│   │   ├── agent.py            # Central orchestrator (STT -> LLM -> Tools -> TTS)
│   │   ├── llm.py              # Gemini client + Local Intent engine
│   │   ├── conversation.py     # Conversation context buffer
│   │   ├── memory.py           # Long-term memory store & context prompt injector
│   │   └── guardrails.py       # Two-step confirmation safety system
│   ├── voice/
│   │   ├── stt.py              # Speech-to-Text recognizer
│   │   └── tts.py              # Text-to-Speech synthesizer
│   ├── tools/
│   │   ├── registry.py         # Tool registry and Gemini schema generator
│   │   ├── search.py           # DuckDuckGo and Wikipedia search
│   │   ├── files.py            # File reading, listing, and document creation
│   │   ├── reminders.py        # Reminder service + background daemon
│   │   ├── calendar.py         # Calendar event management
│   │   └── system.py           # Hardware vitals, app launcher, screenshots, power
│   └── web/
│       ├── server.py           # FastAPI app & WebSockets
│       └── static/
│           ├── index.html      # Sci-Fi Arc Reactor HUD
│           ├── css/hud.css     # Glassmorphic cybernetic theme
│           └── js/
│               ├── app.js      # App controller (STT, TTS, WebSockets)
│               └── visualizer.js # Canvas audio waveform visualizer
└── data/
    ├── documents/              # Created user documents and notes
    ├── reminders.json          # Persistent reminders
    ├── calendar.json           # Scheduled calendar events
    └── memory.json             # Remembered user facts
```

---

## 🔐 Safety & Guardrails Example

When a dangerous action is commanded (e.g., deleting a file or executing a system command):

```
User: "Delete the file sprint_goals.txt"
MINE: "I require your confirmation to permanently delete 'sprint_goals.txt'. Shall I proceed?"
Status: PENDING_CONFIRMATION

User: "No, cancel that."
MINE: "Action cancelled. Safe state restored, Sir."

User: "Delete the file sprint_goals.txt"
MINE: "I require your confirmation to permanently delete 'sprint_goals.txt'. Shall I proceed?"
User: "Yes, proceed."
MINE: "Action authorized, Sir. File 'sprint_goals.txt' has been permanently deleted."
```
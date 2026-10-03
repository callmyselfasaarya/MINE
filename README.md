# M.I.N.E MVP

> **M.I.N.E.** — A real, functional personal desktop AI assistant built with modern voice recognition, function-calling tools, conversation context, hardware telemetry, and two-step safety guardrails.

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

MINE uses a **smart two-pass pipeline** for every input:

```
User Input
    │
    ▼
┌─────────────────────────────────┐
│  Local Intent Engine (instant)  │  ◄── Tool commands (greet, open app,
│  Pattern-matched, zero latency  │       search, reminders, notes, etc.)
└────────────────┬────────────────┘
                 │ No intent matched (out-of-context question)
                 ▼
┌─────────────────────────────────────┐
│  Ollama / Gemini  (conversational)  │  ◄── General knowledge, reasoning,
│  Full LLM for free-form replies     │       coding help, explanations, etc.
└─────────────────────────────────────┘
```

This means **tool commands are always instant** (no LLM needed), while **any question Ollama doesn't recognize** gets answered naturally by the local LLM.

---

**Option 1: Ollama Local LLM (Default & Recommended for 100% Privacy)**

MINE integrates with [Ollama](https://ollama.com/) for entirely local, private, and offline-capable intelligence.

**Step 1 — Install Ollama:**
```bash
# Download from https://ollama.com/download (Windows installer available)
# Or via winget:
winget install Ollama.Ollama
```

**Step 2 — Pull a model:**
```bash
# Default model (recommended, fast, good quality)
ollama pull llama3.2

# Alternatives (pick based on your VRAM):
ollama pull llama3.1        # Larger, smarter
ollama pull mistral         # Fast and capable
ollama pull phi3            # Lightweight for low-end machines
ollama pull gemma2          # Google's open model
```

**Step 3 — Start Ollama daemon:**
```bash
ollama serve
# Ollama runs at http://localhost:11434 by default
```

**Step 4 — Configure `.env`:**
```env
LLM_PROVIDER=ollama
OLLAMA_HOST=http://localhost:11434
OLLAMA_URL=http://localhost:11434/api/chat
OLLAMA_MODEL=llama3.2
OLLAMA_TIMEOUT=25
```

**How out-of-context questions are handled:**

When you ask something MINE's intent engine doesn't recognize (e.g. *"Explain black holes"*, *"Write me a poem"*, *"What is the capital of France?"*), it automatically routes to Ollama:

```
You:   "What is the speed of light?"
MINE:  [Local engine: no intent match]
       [Routing to Ollama (llama3.2) for conversational answer...]
MINE:  "The speed of light in a vacuum is approximately 299,792,458
        metres per second (about 3×10⁸ m/s), often denoted as 'c'."
```

If Ollama is offline, MINE gracefully falls back with a helpful offline message.

---

**Option 2: Google Gemini (Cloud Reasoning)**

Add your free Gemini API key from [Google AI Studio](https://aistudio.google.com/app/apikey) in `.env`:
```env
LLM_PROVIDER=gemini
GEMINI_API_KEY=your_gemini_api_key_here
GEMINI_MODEL=gemini-2.5-flash
```

> **Tip:** You can run both — set `LLM_PROVIDER=ollama` and also add a `GEMINI_API_KEY`. MINE will use Ollama first, falling back to Gemini, then the local engine.

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
Run MINE purely from the command line with rich formatting and hands-free voice:
```bash
python main.py --cli
```
- **🎙️ Mic Mode (Primary by default)**: The assistant speaks its greeting and immediately listens for your voice commands hands-free. After each response, it automatically listens for your next request.
- **🛡️ Voice Source Differentiation**: System Voice (TTS/speaker output) and Microphone Voice (user speech) are actively arbitrated. The microphone will not record while the assistant is speaking, and acoustic reflections from speakers are recognized and discarded.
- **⌨️ Keyboard Mode**: Press `[Enter]` or say `"switch to text"` to switch to typing mode (`python main.py --cli --text` forces text mode).
- **Voice Diagnostic Commands**: Type `/voice status` in text mode to inspect real-time voice differentiation metrics or `/voice echo [on|off]` to toggle echo cancellation.
- **Mode Switching**: Type `/mic` to return to continuous voice mode, `/text` for text mode, or `/wake` to toggle wake-word standby.
- Displays live tool execution traces and confirmation dialogs.

---

## 🎙️ Voice Differentiation & Anti-Overlap Architecture

To eliminate audio overlapping, self-triggering, and acoustic feedback loops, M.I.N.E. features a dedicated **Voice Arbiter** (`jarvis.voice.arbiter`):

```
┌────────────────────────────────────────────────────────┐
│               M.I.N.E. VOICE ARBITER                   │
├──────────────────────────┬─────────────────────────────┤
│   🔊 SYSTEM VOICE        │      🎙️ MICROPHONE VOICE     │
│   (TTS / SAPI / Output)  │      (User Input / STT)     │
├──────────────────────────┼─────────────────────────────┤
│ • Tracks playback state  │ • Pre-listen wait for quiet │
│ • History of utterances  │ • Acoustic cooldown buffer  │
│ • Prevents dual playback │ • Multi-signature echo test │
│ • Broadcasts sync events │ • Filters speaker bleed     │
└──────────────────────────┴─────────────────────────────┘
```

1. **Active State Synchronization**: The microphone stream never opens while the system voice is speaking.
2. **Acoustic Cooldown**: An acoustic settling window (default `0.45s`) allows room reverberation and hardware audio buffers to clear before listening starts.
3. **Multi-Signature Echo Rejection**: Any audio captured from the microphone is differentiated against recent system utterances using:
   - Exact match comparison
   - Substring & fragment detection (e.g., catching tails of assistant sentences)
   - Sequence similarity scoring (`difflib` ratio threshold)
   - Token overlap & coverage (Jaccard similarity)
   - Wake-word self-bleed detection (prevents assistant from waking itself when it mentions its name)
4. **Dual Playback Elimination**: Server SAPI and browser Web Speech synthesis are coordinated via WebSocket events so the system never speaks over itself with two voices.

---

## 🧪 Testing

Run the automated test suite to verify voice differentiation, acoustic echo cancellation, and core functionality:
```bash
python -m unittest discover tests
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
├── tests/                      # Automated test suite
│   ├── test_voice_arbiter.py   # Unit tests for Voice Arbiter & echo filtering
│   └── test_voice_integration.py # Integration tests for STT, TTS, and Arbiter
├── jarvis/                     # Core system modules
│   ├── config.py               # Settings, paths, and system prompts
│   ├── cli.py                  # Rich terminal CLI interface with /voice command
│   ├── core/
│   │   ├── agent.py            # Central orchestrator (STT -> LLM -> Tools -> TTS)
│   │   ├── llm.py              # Gemini/Ollama client + Local Intent engine
│   │   │                       # └─ Out-of-context queries → Ollama conversational fallback
│   │   ├── conversation.py     # Conversation context buffer
│   │   ├── memory.py           # Long-term memory store & context prompt injector
│   │   └── guardrails.py       # Two-step confirmation safety system
│   ├── voice/
│   │   ├── arbiter.py          # Voice Arbiter: source differentiator & acoustic echo cancellation
│   │   ├── stt.py              # Speech-to-Text recognizer with echo suppression
│   │   ├── tts.py              # Text-to-Speech synthesizer with acoustic settling
│   │   └── wake_word.py        # Background wake-word engine with self-trigger bleed rejection
│   ├── tools/
│   │   ├── registry.py         # Tool registry and Gemini/Ollama schema generator
│   │   ├── search.py           # DuckDuckGo and Wikipedia search
│   │   ├── files.py            # File reading, listing, and document creation
│   │   ├── reminders.py        # Reminder service + background daemon
│   │   ├── calendar.py         # Calendar event management
│   │   ├── system.py           # Hardware vitals, app launcher, screenshots, power
│   │   └── entertainment.py    # Jokes, music playback, website opener, Google search,
│   │                           # save notes, time-aware greeting (greet_user)
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
    │   └── important_notes.txt # Timestamped notes saved via "take a note"
    ├── screenshots/            # Screenshots saved via "take a screenshot"
    ├── reminders.json          # Persistent reminders
    ├── calendar.json           # Scheduled calendar events
    └── memory.json             # Remembered user facts
```
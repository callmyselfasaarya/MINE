import asyncio
import json
import logging
from pathlib import Path
from typing import Any, Dict, List

from fastapi import FastAPI, WebSocket, WebSocketDisconnect, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import FileResponse, HTMLResponse
from fastapi.staticfiles import StaticFiles
from pydantic import BaseModel

from jarvis.config import ASSISTANT_NAME, USER_NAME, DOCUMENTS_DIR
from jarvis.core.agent import jarvis_agent
from jarvis.voice.tts import register_speech_listener
from jarvis.tools.reminders import register_reminder_listener

logger = logging.getLogger(__name__)

app = FastAPI(title="M.I.N.E Personal Assistant", version="1.0.0")

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

STATIC_DIR = Path(__file__).parent / "static"
app.mount("/static", StaticFiles(directory=str(STATIC_DIR)), name="static")

# Connected WebSockets
active_connections: List[WebSocket] = []


async def broadcast_ws(payload: Dict[str, Any]):
    dead_connections = []
    for ws in active_connections:
        try:
            await ws.send_json(payload)
        except Exception:
            dead_connections.append(ws)
    for ws in dead_connections:
        if ws in active_connections:
            active_connections.remove(ws)


# Hook agent events to WebSockets
def on_agent_event(payload: Dict[str, Any]):
    try:
        loop = asyncio.get_event_loop()
        if loop.is_running():
            asyncio.create_task(broadcast_ws(payload))
    except RuntimeError:
        pass

jarvis_agent.register_event_listener(on_agent_event)

# Hook speech & reminder triggers to WebSockets
def on_speech(text: str):
    on_agent_event({"event": "tts_speech", "data": {"text": text}})

register_speech_listener(on_speech)

def on_reminder_trigger(reminder: Dict[str, Any]):
    on_agent_event({"event": "reminder_triggered", "data": reminder})

register_reminder_listener(on_reminder_trigger)


class ChatRequest(BaseModel):
    message: str
    speak: bool = False  # Browser web TTS handles audio playback if false


class SettingsRequest(BaseModel):
    gemini_api_key: str = ""
    model_name: str = ""


class ReminderRequest(BaseModel):
    title: str
    due_time: str
    note: str = ""


class CalendarRequest(BaseModel):
    title: str
    date_str: str
    time_str: str
    duration_minutes: int = 60
    description: str = ""


class MemoryRequest(BaseModel):
    topic: str
    information: str
    category: str = "general"


class DocumentRequest(BaseModel):
    filename: str
    content: str


@app.get("/", response_class=HTMLResponse)
async def serve_index():
    index_file = STATIC_DIR / "index.html"
    return FileResponse(index_file)


@app.get("/api/state")
async def get_state():
    return jarvis_agent.get_dashboard_state()


@app.post("/api/chat")
async def chat_endpoint(req: ChatRequest):
    result = jarvis_agent.interact(req.message, speak_output=req.speak)
    state = jarvis_agent.get_dashboard_state()
    return {
        "result": result,
        "state": state
    }


@app.post("/api/action/confirm")
async def confirm_action():
    result = jarvis_agent.confirm_action()
    return {"result": result, "state": jarvis_agent.get_dashboard_state()}


@app.post("/api/action/cancel")
async def cancel_action():
    result = jarvis_agent.cancel_action()
    return {"result": result, "state": jarvis_agent.get_dashboard_state()}


@app.post("/api/voice/listen")
async def trigger_server_mic():
    """Trigger server-side microphone listen turn."""
    turn = jarvis_agent.voice_turn(timeout=6.0)
    return {"result": turn, "state": jarvis_agent.get_dashboard_state()}


@app.post("/api/settings")
async def update_settings(req: SettingsRequest):
    if req.gemini_api_key:
        jarvis_agent.llm.reload_key(req.gemini_api_key)
    if req.model_name:
        jarvis_agent.llm.model_name = req.model_name
    return {"success": True, "gemini_active": jarvis_agent.llm.is_gemini_active(), "model": jarvis_agent.llm.model_name}


@app.post("/api/reminders")
async def add_reminder(req: ReminderRequest):
    from jarvis.tools.reminders import create_reminder
    res = create_reminder(req.title, req.due_time, req.note)
    return {"result": res, "state": jarvis_agent.get_dashboard_state()}


@app.delete("/api/reminders/{reminder_id}")
async def remove_reminder(reminder_id: str):
    from jarvis.tools.reminders import delete_reminder
    res = delete_reminder(reminder_id)
    return {"result": res, "state": jarvis_agent.get_dashboard_state()}


@app.post("/api/calendar")
async def add_calendar(req: CalendarRequest):
    from jarvis.tools.calendar import create_calendar_event
    res = create_calendar_event(req.title, req.date_str, req.time_str, req.duration_minutes, req.description)
    return {"result": res, "state": jarvis_agent.get_dashboard_state()}


@app.delete("/api/calendar/{event_id}")
async def remove_calendar(event_id: str):
    from jarvis.tools.calendar import delete_calendar_event
    res = delete_calendar_event(event_id)
    return {"result": res, "state": jarvis_agent.get_dashboard_state()}


@app.post("/api/memory")
async def add_memory(req: MemoryRequest):
    from jarvis.core.memory import remember_fact
    res = remember_fact(req.topic, req.information, req.category)
    return {"result": res, "state": jarvis_agent.get_dashboard_state()}


@app.delete("/api/memory/{key}")
async def remove_memory(key: str):
    from jarvis.core.memory import forget_fact
    res = forget_fact(key)
    return {"result": res, "state": jarvis_agent.get_dashboard_state()}


@app.get("/api/documents")
async def get_documents():
    from jarvis.tools.files import list_files
    return list_files()


@app.get("/api/documents/{filename}")
async def get_document(filename: str):
    from jarvis.tools.files import read_file
    res = read_file(filename)
    if not res.get("success"):
        raise HTTPException(status_code=404, detail=res.get("error"))
    return res


@app.post("/api/documents")
async def save_document(req: DocumentRequest):
    from jarvis.tools.files import create_document
    res = create_document(req.filename, req.content)
    return {"result": res, "state": jarvis_agent.get_dashboard_state()}


@app.websocket("/ws")
async def websocket_endpoint(websocket: WebSocket):
    await websocket.accept()
    active_connections.append(websocket)
    try:
        # Send initial state immediately
        await websocket.send_json({
            "event": "initial_state",
            "data": jarvis_agent.get_dashboard_state()
        })
        while True:
            msg = await websocket.receive_text()
            data = json.loads(msg)
            # Handle incoming WS message if any
            if data.get("action") == "ping":
                await websocket.send_json({"event": "pong"})
    except WebSocketDisconnect:
        if websocket in active_connections:
            active_connections.remove(websocket)
    except Exception as e:
        logger.error(f"WebSocket error: {e}")
        if websocket in active_connections:
            active_connections.remove(websocket)
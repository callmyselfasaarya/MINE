import asyncio
import json
import logging
from pathlib import Path
from typing import Any, Dict, List, Optional

from fastapi import FastAPI, WebSocket, WebSocketDisconnect, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import FileResponse, HTMLResponse
from fastapi.staticfiles import StaticFiles
from pydantic import BaseModel

from jarvis.config import ASSISTANT_NAME, USER_NAME, DOCUMENTS_DIR
from jarvis.core.agent import jarvis_agent
from jarvis.voice.tts import tts, register_speech_listener
from jarvis.voice.arbiter import voice_arbiter
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

# Hook voice arbiter events (system_voice_start, system_voice_end, mic_listen_start, etc.) to WebSockets
def on_voice_arbiter_event(event_type: str, data: Dict[str, Any]):
    on_agent_event({"event": event_type, "data": data})

voice_arbiter.register_state_listener(on_voice_arbiter_event)

# Hook speech & reminder triggers to WebSockets
def on_speech(text: str):
    on_agent_event({
        "event": "tts_speech",
        "data": {
            "text": text,
            "server_audio_active": (tts.speaker is not None and tts.enabled)
        }
    })

register_speech_listener(on_speech)

def on_reminder_trigger(reminder: Dict[str, Any]):
    on_agent_event({"event": "reminder_triggered", "data": reminder})

register_reminder_listener(on_reminder_trigger)


class ChatRequest(BaseModel):
    message: str
    speak: bool = False  # Browser web TTS handles audio playback if false


class SettingsRequest(BaseModel):
    provider: str = ""
    ollama_model: str = ""
    ollama_url: str = ""
    gemini_api_key: str = ""
    gemini_model: str = ""


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
    status = jarvis_agent.llm.configure(
        provider=req.provider or None,
        ollama_model=req.ollama_model or None,
        ollama_url=req.ollama_url or None,
        gemini_api_key=req.gemini_api_key if req.gemini_api_key != "" else None,
        gemini_model=req.gemini_model or None
    )
    return {"success": True, "settings": status, "state": jarvis_agent.get_dashboard_state()}


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


class SmartHomeStateRequest(BaseModel):
    device_id: str
    state: str
    brightness: Optional[int] = None
    temperature: Optional[float] = None


class SmartSceneRequest(BaseModel):
    scene: str


class SubAgentRequest(BaseModel):
    task: str


class SemanticSearchRequest(BaseModel):
    query: str
    top_k: int = 4


@app.get("/api/perception/sensors")
async def get_sensors():
    return jarvis_agent.perception.sensors.get_snapshot()


@app.post("/api/perception/screen")
async def inspect_screen():
    return jarvis_agent.perception.inspect_visual_context()


@app.post("/api/perception/ocr")
async def read_screen_ocr():
    return jarvis_agent.perception.ocr.read_screen_text()


@app.post("/api/perception/camera")
async def capture_camera():
    return jarvis_agent.perception.vision.capture_camera_frame()


@app.post("/api/agents/research")
async def invoke_research(req: SubAgentRequest):
    result = jarvis_agent.agents.dispatch("research", req.task)
    return {"result": result, "state": jarvis_agent.get_dashboard_state()}


@app.post("/api/agents/coding")
async def invoke_coding(req: SubAgentRequest):
    result = jarvis_agent.agents.dispatch("coding", req.task)
    return {"result": result, "state": jarvis_agent.get_dashboard_state()}


@app.post("/api/agents/planning")
async def invoke_planning(req: SubAgentRequest):
    result = jarvis_agent.planner.create_and_execute_plan(req.task)
    return {"result": result, "state": jarvis_agent.get_dashboard_state()}


@app.get("/api/smart-home")
async def get_smart_home():
    return jarvis_agent.execution.smart_home.list_devices()


@app.post("/api/smart-home/state")
async def set_smart_home_state(req: SmartHomeStateRequest):
    res = jarvis_agent.execution.smart_home.set_device_state(
        req.device_id, req.state, req.brightness, req.temperature
    )
    return {"result": res, "state": jarvis_agent.get_dashboard_state()}


@app.post("/api/smart-home/scene")
async def trigger_smart_scene_endpoint(req: SmartSceneRequest):
    res = jarvis_agent.execution.smart_home.trigger_scene(req.scene)
    return {"result": res, "state": jarvis_agent.get_dashboard_state()}


@app.post("/api/memory/semantic")
async def search_semantic(req: SemanticSearchRequest):
    res = jarvis_agent.memory.semantic.search(req.query, top_k=req.top_k)
    return {"results": res, "count": len(res)}


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
from fastapi import APIRouter, UploadFile, File, WebSocket, WebSocketDisconnect, HTTPException
from fastapi.responses import JSONResponse, Response
from backend.models import VoiceQuery, APIResponse
import shutil
import os
import base64
from io import BytesIO

from contextlib import asynccontextmanager
from fastapi import FastAPI

# Global AI Engine instance
ai_engine = None
stt_model = None

@asynccontextmanager
async def lifespan(app: FastAPI):
    # Load AI Engine on startup
    global ai_engine, stt_model
    print("--- STARTUP: Loading AI Engine ---")
    try:
        from backend.ai_engine import ai_engine as engine
        ai_engine = engine
        # Force initialization if it's a lazy proxy
        if hasattr(ai_engine, 'query'):
            print("AI Engine loaded successfully.")
        else:
            print("AI Engine loaded (lazy proxy).")
    except Exception as e:
        print(f"CRITICAL: Failed to load AI Engine: {e}")
        import traceback
        traceback.print_exc()
    
    # Load Whisper Model on startup
    print("--- STARTUP: Loading Whisper Model ---")
    try:
        from faster_whisper import WhisperModel
        stt_model = WhisperModel("tiny", device="cpu", compute_type="int8")
        print("Whisper Model loaded successfully.")
    except Exception as e:
        print(f"WARNING: Failed to load Whisper Model: {e}")

    yield
    
    # Cleanup if needed
    print("--- SHUTDOWN ---")

def get_ai_engine():
    return ai_engine

def get_stt_model():
    return stt_model




router = APIRouter()

# Health check endpoint
@router.get("/health")
async def health_check():
    """Simple health check endpoint - doesn't require AI engine."""
    return {"status": "ok", "message": "Backend is running"}

# Global connection manager for WebSockets
class ConnectionManager:
    def __init__(self):
        self.active_connections: list[WebSocket] = []

    async def connect(self, websocket: WebSocket):
        await websocket.accept()
        self.active_connections.append(websocket)

    def disconnect(self, websocket: WebSocket):
        self.active_connections.remove(websocket)

    async def broadcast(self, message: str):
        for connection in self.active_connections:
            await connection.send_text(message)

manager = ConnectionManager()

# Global Whisper Model Load - lazy load to avoid startup issues


@router.post("/stt")
async def speech_to_text(file: UploadFile = File(...)):
    """
    Receives an audio file, saves it temporarily, and runs simple STT using faster-whisper model.
    """
    temp_filename = f"temp_{file.filename}"
    with open(temp_filename, "wb") as buffer:
        shutil.copyfileobj(file.file, buffer)
    
    text = "Error processing voice input."
    
    stt = get_stt_model()
    if stt:
        try:
            segments, info = stt.transcribe(temp_filename)
            text = "".join([segment.text for segment in segments])
        except Exception as e:
            print(f"STT Error: {e}")
    else:
        print("STT Model not available.")
    
    os.remove(temp_filename)
    return {"text": text}

@router.post("/rag-query", response_model=APIResponse)
async def query_ai(query: VoiceQuery):
    """
    Main interaction endpoint.
    1. Query AI Engine (RAG + LLM)
    2. Generate TTS audio for the response
    3. Return structured data + audio
    """
    engine = get_ai_engine()
    
    if engine is None:
        return APIResponse(
            response_text="AI engine is not available. Please check backend logs.",
            audio_base64="",
            order=None
        )
    
    try:
        ai_result = engine.query(query.text)
        response_text = ai_result.get("response_text", "I am sorry, I am broken.")
        order_data = ai_result.get("order")
        
        # Generate Audio
        audio_b64 = ""
        # Generate Audio
        audio_b64 = ""
        try:
            import pyttsx3
            import os
            import uuid
            
            # Create a unique temp file
            temp_file = f"temp_tts_{uuid.uuid4()}.wav"
            
            engine_tts = pyttsx3.init()
            # Optional: Configure voice properties here (rate, volume)
            engine_tts.setProperty('rate', 150) 
            
            # Save to file
            engine_tts.save_to_file(response_text, temp_file)
            engine_tts.runAndWait()
            
            # Read back and encode
            if os.path.exists(temp_file):
                with open(temp_file, "rb") as f:
                    audio_b64 = base64.b64encode(f.read()).decode('utf-8')
                os.remove(temp_file)
            
        except Exception as e:
            print(f"TTS Error (pyttsx3): {e}")
        
        # Broadcast order to Kitchen Display if an order exists
        if order_data:
            import json
            await manager.broadcast(json.dumps(order_data))

        return APIResponse(
            response_text=response_text,
            audio_base64=audio_b64,
            order=order_data
        )
    except Exception as e:
        print(f"Query error: {e}")
        return APIResponse(
            response_text=f"Error: {str(e)}",
            audio_base64="",
            order=None
        )

@router.websocket("/ws")
async def websocket_endpoint(websocket: WebSocket):
    await manager.connect(websocket)
    try:
        while True:
            data = await websocket.receive_text()
            # Echo or process incoming messages from display
    except WebSocketDisconnect:
        manager.disconnect(websocket)

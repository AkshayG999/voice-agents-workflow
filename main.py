from __future__ import annotations

import asyncio
import os
import json
from typing import List, Dict, Any, Optional

import numpy as np
from fastapi import FastAPI, WebSocket, WebSocketDisconnect
from fastapi.responses import HTMLResponse
from fastapi.staticfiles import StaticFiles
from fastapi.middleware.cors import CORSMiddleware
import uvicorn

from agents.voice import StreamedAudioInput, VoicePipeline
from voice_agents import MyWorkflow

SAMPLE_RATE = 24000
FORMAT = np.int16
CHANNELS = 1

app = FastAPI()

# Add CORS middleware to allow cross-origin requests
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],  # Allows all origins
    allow_credentials=True,
    allow_methods=["*"],  # Allows all methods
    allow_headers=["*"],  # Allows all headers
)

# Create a directory for static files if it doesn't exist
static_dir = os.path.join(os.path.dirname(__file__), "static")
os.makedirs(static_dir, exist_ok=True)

# Mount static files directory
app.mount("/static", StaticFiles(directory=static_dir), name="static")

class ConnectionManager:
    def __init__(self):
        self.active_connections: List[WebSocket] = []

    async def connect(self, websocket: WebSocket):
        await websocket.accept()
        self.active_connections.append(websocket)

    def disconnect(self, websocket: WebSocket):
        self.active_connections.remove(websocket)

    async def send_text(self, message: str, websocket: WebSocket):
        await websocket.send_text(message)

    async def send_audio(self, audio_data, websocket: WebSocket):
        await websocket.send_bytes(audio_data.tobytes())

manager = ConnectionManager()

@app.get("/", response_class=HTMLResponse)
async def get():
    with open(os.path.join(static_dir, "index.html")) as f:
        return HTMLResponse(content=f.read())

class StreamedAudioInputWithEndDetection(StreamedAudioInput):
    """An extension of StreamedAudioInput that handles end-of-speech detection."""
    
    def __init__(self):
        super().__init__()
        self.end_of_speech_detected = asyncio.Event()
    
    async def add_audio(self, audio_data: np.ndarray) -> None:
        """Add audio data to the stream."""
        await super().add_audio(audio_data)
    
    def signal_end_of_speech(self) -> None:
        """Signal that the end of speech has been detected."""
        self.end_of_speech_detected.set()
    
    async def wait_for_end_of_speech(self, timeout: Optional[float] = None) -> bool:
        """Wait for end of speech signal or timeout."""
        try:
            await asyncio.wait_for(self.end_of_speech_detected.wait(), timeout)
            return True
        except asyncio.TimeoutError:
            return False

@app.websocket("/ws")
async def websocket_endpoint(websocket: WebSocket):
    await manager.connect(websocket)
    audio_input = StreamedAudioInputWithEndDetection()
    
    pipeline = VoicePipeline(
        workflow=MyWorkflow(
            secret_word="dog", 
            on_start=lambda transcription: handle_transcription(transcription, websocket),
            on_response=lambda response: handle_agent_response(response, websocket)
        )
    )
    
    # Start the pipeline in the background
    pipeline_task = asyncio.create_task(run_pipeline(pipeline, audio_input, websocket))
    
    try:
        while True:
            # Receive data from the client
            data = await websocket.receive()
            
            if "bytes" in data:
                # Process binary audio data
                audio_data = np.frombuffer(data["bytes"], dtype=np.int16)
                await audio_input.add_audio(audio_data)
            elif "text" in data:
                # Process text messages (like end_of_speech)
                try:
                    message = json.loads(data["text"])
                    if message.get("type") == "end_of_speech":
                        audio_input.signal_end_of_speech()
                        await manager.send_text(json.dumps({
                            "type": "lifecycle",
                            "event": "processing_speech"
                        }), websocket)
                except json.JSONDecodeError:
                    pass  # Not JSON, ignore
            
    except WebSocketDisconnect:
        manager.disconnect(websocket)
        pipeline_task.cancel()
        
async def run_pipeline(pipeline, audio_input, websocket):
    try:
        result = await pipeline.run(audio_input)
        
        # Process streaming results
        buffer_size = 0
        audio_buffer = None
        
        async for event in result.stream():
            if event.type == "voice_stream_event_audio":
                if event.data is not None:
                    # Instead of sending tiny audio chunks, buffer them to reasonable sizes
                    # to avoid overwhelming the client with too many small audio fragments
                    if audio_buffer is None:
                        audio_buffer = event.data
                        buffer_size = len(event.data)
                    else:
                        audio_buffer = np.concatenate((audio_buffer, event.data))
                        buffer_size += len(event.data)
                    
                    # Send once we have a reasonable chunk size or if buffer size is large enough
                    if buffer_size >= 4800:  # About 200ms at 24kHz
                        await manager.send_audio(audio_buffer, websocket)
                        audio_buffer = None
                        buffer_size = 0
            elif event.type == "voice_stream_event_lifecycle":
                # Flush any remaining audio before sending lifecycle events
                if audio_buffer is not None and buffer_size > 0:
                    await manager.send_audio(audio_buffer, websocket)
                    audio_buffer = None
                    buffer_size = 0
                
                await manager.send_text(json.dumps({
                    "type": "lifecycle",
                    "event": event.event
                }), websocket)
                
                # Signal completion to restart listening
                if event.event == "completed":
                    await manager.send_text(json.dumps({
                        "type": "processing_complete"
                    }), websocket)
        
        # Send any remaining buffered audio
        if audio_buffer is not None and buffer_size > 0:
            await manager.send_audio(audio_buffer, websocket)
    
    except Exception as e:
        await manager.send_text(json.dumps({
            "type": "error",
            "message": str(e)
        }), websocket)
        
        # Even on error, signal completion to restart listening
        await manager.send_text(json.dumps({
            "type": "processing_complete"
        }), websocket)

async def handle_transcription(transcription: str, websocket: WebSocket):
    print(f"Transcription: {transcription}")
    await manager.send_text(f"{{\"type\": \"transcription\", \"text\": \"{transcription}\"}}", websocket)

async def handle_agent_response(response: str, websocket: WebSocket):
    print(f"Agent response: {response}")
    await manager.send_text(f"{{\"type\": \"agent_response\", \"text\": \"{response}\"}}", websocket)
    
    
if __name__ == "__main__":
    host = "0.0.0.0"
    port = 8000
    
    is_https = os.environ.get("HTTPS", "").lower() == "true"
    
    print(f"\n{'='*50}")
    print(f"Starting server on http{'s' if is_https else ''}://{'localhost'}:{port}")
    if not is_https:
        print("\nWARNING: Running in non-HTTPS mode.")
        print("Browser microphone access may be restricted.")
        print("For local development, access via 'localhost' instead of IP address")
        print("or use a tool like ngrok to create a secure tunnel.")
    print(f"{'='*50}\n")
    
    uvicorn.run(
        "main:app", 
        host=host, 
        port=port,
        reload=True,
        ssl_keyfile=os.environ.get("SSL_KEY"),
        ssl_certfile=os.environ.get("SSL_CERT")
    )

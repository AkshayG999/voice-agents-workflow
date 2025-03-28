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

from agents.voice import (
    StreamedAudioInput,
    VoicePipeline,
    VoicePipelineConfig,
    STTModelSettings,
)
from healthcare_agents.workflow.voice_workflow import HealthcareVoiceWorkflow


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
        self.audio_buffer = np.array([], dtype=np.int16)
        self.silence_frames = 0
        self.max_silence_frames = 30  # About 1.25 seconds at 24kHz with 1024 frames

    async def add_audio(self, audio_data: np.ndarray) -> None:
        """Add audio data to the stream with preprocessing."""
        # Add to buffer first for potential preprocessing
        self.audio_buffer = np.append(self.audio_buffer, audio_data)

        # Process in chunks to avoid excessive memory usage
        if len(self.audio_buffer) > 24000:  # Process about 1 second of audio at a time
            # Simple energy-based silence detection
            energy = np.mean(np.abs(self.audio_buffer))
            if energy < 100:  # Silence threshold
                self.silence_frames += 1
            else:
                self.silence_frames = 0

            # Pass the audio to the base class for processing
            await super().add_audio(self.audio_buffer)
            self.audio_buffer = np.array([], dtype=np.int16)

    def signal_end_of_speech(self) -> None:
        """Signal that the end of speech has been detected."""
        # Process any remaining audio in buffer before ending
        if len(self.audio_buffer) > 0:
            asyncio.create_task(super().add_audio(self.audio_buffer))
            self.audio_buffer = np.array([], dtype=np.int16)
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

    # Model configuration with fallbacks
    try:
        # Try to use the most advanced model first
        stt_settings = STTModelSettings(
            prompt="you are an advanced speech-to-text transcription AI. Your task is to accurately transcribe spoken English audio into written text. Ensure proper grammar, punctuation, and formatting while preserving the speaker's intent. Handle different accents and background noise effectively. If the audio is unclear, indicate uncertain words using [inaudible] or [unclear] instead of guessing. Maintain paragraph structure for readability.",
            language="en-US",
            turn_detection={
                "type": "server_vad",
                "threshold": 0.5,
                "prefix_padding_ms": 300,
                "silence_duration_ms": 200,
            },
            temperature=0.0,
        )
    except Exception as e:
        print(f"Error configuring advanced STT settings: {str(e)}")
        # Fallback to basic settings if advanced ones fail
        stt_settings = STTModelSettings(
            # prompt="you are an advanced speech-to-text transcription AI. Your task is to accurately transcribe spoken English audio into written text. Ensure proper grammar, punctuation, and formatting while preserving the speaker's intent. Handle different accents and background noise effectively. If the audio is unclear, indicate uncertain words using [inaudible] or [unclear] instead of guessing. Maintain paragraph structure for readability.",
            # language="en-US",
            language="hi",
            turn_detection={"type": "server_vad"},
        )

    pipeline = VoicePipeline(
        workflow=HealthcareVoiceWorkflow(
            secret_word="Health",
            on_start=lambda transcription: handle_transcription(
                transcription, websocket
            ),
            on_response=lambda response: handle_agent_response(response, websocket),
        ),
        config=VoicePipelineConfig(
            stt_settings=stt_settings,
            workflow_name="Healthcare Voice Workflow",
            group_id="healthcare",
            trace_metadata={"source": "voice"},
        ),
    )

    # Start the pipeline in the background
    pipeline_task = asyncio.create_task(run_pipeline(pipeline, audio_input, websocket))

    try:
        while True:
            # Receive data from the client
            data = await websocket.receive()

            if "bytes" in data:
                # Process binary audio data
                try:
                    audio_data = np.frombuffer(data["bytes"], dtype=np.int16)
                    # Check for very low energy audio and skip if needed
                    energy = np.mean(np.abs(audio_data))
                    if energy < 50:  # Very low energy threshold
                        continue  # Skip processing this chunk

                    await audio_input.add_audio(audio_data)
                except Exception as e:
                    print(f"Error processing audio data: {str(e)}")
            elif "text" in data:
                # Process text messages (like end_of_speech)
                try:
                    message = json.loads(data["text"])
                    if message.get("type") == "end_of_speech":
                        audio_input.signal_end_of_speech()
                        await manager.send_text(
                            json.dumps(
                                {"type": "lifecycle", "event": "processing_speech"}
                            ),
                            websocket,
                        )
                except json.JSONDecodeError:
                    pass  # Not JSON, ignore
                except Exception as e:
                    print(f"Error processing message: {str(e)}")

    except WebSocketDisconnect:
        manager.disconnect(websocket)
        pipeline_task.cancel()
    except Exception as e:
        print(f"Unexpected error in websocket handler: {str(e)}")
        try:
            await manager.send_text(
                json.dumps({"type": "error", "message": f"Server error: {str(e)}"}),
                websocket,
            )
        except:
            pass
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

                await manager.send_text(
                    json.dumps({"type": "lifecycle", "event": event.event}), websocket
                )

                # Signal completion to restart listening
                if event.event == "completed":
                    await manager.send_text(
                        json.dumps({"type": "processing_complete"}), websocket
                    )

        # Send any remaining buffered audio
        if audio_buffer is not None and buffer_size > 0:
            await manager.send_audio(audio_buffer, websocket)

    except Exception as e:
        await manager.send_text(
            json.dumps({"type": "error", "message": str(e)}), websocket
        )

        # Even on error, signal completion to restart listening
        await manager.send_text(json.dumps({"type": "processing_complete"}), websocket)


async def handle_transcription(transcription: str, websocket: WebSocket):
    print(f"Transcription: {transcription}")
    await manager.send_text(
        f'{{"type": "transcription", "text": "{transcription}"}}', websocket
    )


async def handle_agent_response(response: str, websocket: WebSocket):
    print(f"Agent response: {response}")
    message = {"type": "agent_response", "text": response}
    await manager.send_text(json.dumps(message), websocket)


async def on_start(transcription: str):
    """Called when the workflow starts processing a transcription."""
    print(f"Processing: {transcription}")


async def on_response(response: str):
    """Called when the workflow generates a complete response."""
    print(f"Response: {response}")


def main():
    # Create the workflow with a secret word and callbacks
    workflow = HealthcareVoiceWorkflow(
        secret_word="health", on_start=on_start, on_response=on_response
    )

    return workflow


if __name__ == "__main__":
    workflow = main()
    # The workflow can now be used to process voice transcriptions
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
        ssl_certfile=os.environ.get("SSL_CERT"),
    )

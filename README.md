# Healthcare Voice Assistant

The system processes spoken questions about health topics and provides relevant information through both text and synthesized speech responses.

## Features

- Real-time voice input processing
- Automatic routing to specialized healthcare agents (cardiology, neurology, nutrition, etc.)
- Text and voice responses

## Screenshots

![Screenshot 1](https://github.com/AkshayG999/voice-agents-workflow/blob/main/public/image-1.png)
![Screenshot 2](https://github.com/AkshayG999/voice-agents-workflow/blob/main/public/image-2.png)

## Setup

## Installation

1. Clone the repository:
   ```bash
   git clone https://github.com/AkshayG999/voice-agents-workflow.git
   cd voice-agents-workflow
   ```

2. Install the required dependencies:
   ```bash
   pip install -r requirements.txt
   ```

3. Make sure you have appropriate audio drivers installed for your system

## Usage

1. Run the application:
   ```bash
   python main.py
   ```

## Voice Agent Workflow Explanation

The following explains how the voice agent system processes speech-to-text (STT), language model (LLM) answering, and text-to-speech (TTS).

### Complete Voice Agent Workflow

#### Audio Capture (Browser)
- User starts recording by clicking the button
- Browser captures microphone audio via Web Audio API
- Real-time silence detection monitors when the user stops talking
- Audio is converted from Float32 to Int16 format and sent to server via WebSockets

#### Speech-to-Text Processing (Server)
- Server receives audio chunks via /ws WebSocket endpoint
- Audio is fed into StreamedAudioInputWithEndDetection buffer
- When silence is detected, client signals "end_of_speech"
- The VoicePipeline processes the audio stream for transcription
- OpenAI's Whisper model (likely used behind the scenes) converts speech to text

#### Language Understanding & Response (LLM)
- Transcription is passed to MyWorkflow.run() method
- Text is added to conversation history in _input_history
- Runner.run_streamed() processes the query with the appropriate agent:
  - Main agent classifies the query using classify_medical_intent
  - Query is routed to specialized agents (cardiology, nutrition, etc.)
  - Agent uses OpenAI's GPT models to generate a response
  - Function tools (get_weather, get_health_info, etc.) provide external data

#### Text-to-Speech Generation (Server)
- Response text is streamed from the LLM via VoiceWorkflowHelper.stream_text_from()
- Server converts text to speech (likely using OpenAI's TTS API)
- Audio is buffered into reasonable chunks (about 200ms each)
- Audio data is sent back to client as binary WebSocket messages

#### Audio Playback (Browser)
- Browser receives audio chunks and adds them to audioQueue
- processAudioQueue handles sequential playback of chunks
- Each audio chunk is:
  - Converted from Int16 to Float32 format
  - Loaded into an AudioBuffer
  - Played through Web Audio API
- System waits for each chunk to finish before playing the next

#### Conversation Flow
- After playback completes, system returns to listening mode
- restartListening() resets the UI to accept new input
- Conversation history is maintained for context in future exchanges

[User] → Microphone → [Browser] → WebSocket → [Server]
                                              ↓
                                          Audio Buffer
                                              ↓
                                      Speech-to-Text (STT)
                                              ↓
                                      Transcription Text
                                              ↓
                          ┌─────────────LLM Processing──────────────┐
                          │                                         │
                          ↓                                         ↓
                    Main Agent─────────────┬───────────Specialized Agents
                                           │                 │
                                           ↓                 ↓
                                      Function Tools     Function Tools
                          │                                         │
                          └─────────────────────────────────────────┘
                                              ↓
                                       Response Text
                                              ↓
                                    Text-to-Speech (TTS)
                                              ↓
                                        Audio Chunks
                                              ↓
[User] ← Speaker ← [Browser] ← WebSocket ← [Server]
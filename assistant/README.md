# AI Voice Assistant

This project implements a production-style AI Voice Assistant using a client-server architecture.

## Structure

assistant/
├── server/
│   ├── main.py
│   ├── chat.py
│   ├── speech.py
│   ├── vision.py
│   ├── models.py
│   └── requirements.txt
│
├── client/
│   ├── gui.py
│   ├── api.py
│   ├── microphone.py
│   ├── webcam.py
│   ├── speaker.py
│   └── requirements.txt
│
└── README.md

## Setup

1. Install server dependencies:
   ```bash
   python -m pip install -r assistant/server/requirements.txt
   ```
2. Install client dependencies:
   ```bash
   python -m pip install -r assistant/client/requirements.txt
   ```
3. Start server:
   ```bash
   uvicorn assistant.server.main:app --reload --host 127.0.0.1 --port 8000
   ```
4. Start client:
   ```bash
   python assistant/client/gui.py
   ```

## Features

- REST API server with FastAPI
- Llama 3.2 chat via LangChain Ollama
- Vosk speech-to-text
- pyttsx3 text-to-speech WAV generation
- OpenCV vision endpoint
- Tkinter client with webcam preview and audio I/O

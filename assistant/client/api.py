import io
from typing import Optional

import requests


class AssistantAPI:
    def __init__(self, base_url: str = "http://127.0.0.1:8000") -> None:
        self.base_url = base_url.rstrip("/")

    def chat(self, message: str) -> str:
        response = requests.post(f"{self.base_url}/chat", json={"message": message}, timeout=30)
        response.raise_for_status()
        return response.json().get("reply", "")

    def speech_to_text(self, wav_bytes: bytes) -> str:
        files = {"file": ("speech.wav", wav_bytes, "audio/wav")}
        response = requests.post(f"{self.base_url}/speech/stt", files=files, timeout=30)
        response.raise_for_status()
        return response.json().get("text", "")

    def text_to_speech(self, text: str) -> bytes:
        response = requests.post(f"{self.base_url}/speech/tts", json={"text": text}, timeout=30)
        response.raise_for_status()
        return response.content

    def send_frame(self, image_bytes: bytes, filename: str = "frame.jpg") -> dict:
        files = {"image": (filename, image_bytes, "image/jpeg")}
        response = requests.post(f"{self.base_url}/vision", files=files, timeout=30)
        response.raise_for_status()
        return response.json()

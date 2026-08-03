import io
import json
import logging
import os
import tempfile
import threading
import wave

import pyttsx3
import vosk
import speech_recognition as sr
from fastapi import APIRouter, BackgroundTasks, File, HTTPException, UploadFile
from fastapi.responses import FileResponse

from assistant.server.models import STTResponse, TTSRequest

logger = logging.getLogger(__name__)
router = APIRouter()

VOSK_MODEL_PATH = os.environ.get("VOSK_MODEL_PATH", "./models/vosk-model-small-en-us-0.15")
vosk_model = None
if os.path.isdir(VOSK_MODEL_PATH):
    try:
        vosk_model = vosk.Model(VOSK_MODEL_PATH)
    except Exception as exc:
        logger.exception("Failed to initialize Vosk model from %s.", VOSK_MODEL_PATH)
        vosk_model = None
else:
    logger.warning("Vosk model directory not found: %s. STT endpoint will be unavailable.", VOSK_MODEL_PATH)

engine = pyttsx3.init()
engine_lock = threading.Lock()

# Optional audio tuning. Keep defaults if platform voices vary.
try:
    default_rate = engine.getProperty("rate")
    engine.setProperty("rate", max(100, default_rate - 30))
except Exception:
    logger.warning("Unable to adjust pyttsx3 rate.")


def _transcribe_wav(uploaded_file: UploadFile) -> str:
    raw_bytes = uploaded_file.file.read()
    uploaded_file.file.close()

    try:
        with wave.open(io.BytesIO(raw_bytes), "rb") as wav_file:
            sample_rate = wav_file.getframerate()
            channels = wav_file.getnchannels()
            pcm_data = wav_file.readframes(wav_file.getnframes())
    except wave.Error as exc:
        logger.exception("Invalid WAV upload.")
        raise HTTPException(status_code=400, detail="Uploaded file is not a valid WAV audio file.")

    if channels != 1 or sample_rate != 16000:
        logger.error("Unsupported WAV format: channels=%s rate=%s", channels, sample_rate)
        raise HTTPException(
            status_code=400,
            detail="WAV file must be mono and 16000 Hz. Please send a compatible audio file.",
        )

    if vosk_model is not None:
        recognizer = vosk.KaldiRecognizer(vosk_model, sample_rate)
        if not recognizer.AcceptWaveform(pcm_data):
            logger.debug("Partial speech result received.")
            result = recognizer.FinalResult()
        else:
            result = recognizer.Result()

        payload = json.loads(result)
        return payload.get("text", "")

    logger.warning("Vosk model unavailable; using SpeechRecognition fallback.")
    recognizer = sr.Recognizer()
    with sr.AudioFile(io.BytesIO(raw_bytes)) as source:
        audio_data = recognizer.record(source)

    try:
        return recognizer.recognize_google(audio_data)
    except sr.UnknownValueError:
        return ""
    except sr.RequestError as exc:
        logger.exception("Google SpeechRecognition request failed.")
        raise HTTPException(status_code=503, detail="Speech recognition service unavailable.")


def _cleanup_file(path: str) -> None:
    try:
        os.remove(path)
    except OSError:
        logger.warning("Unable to remove temporary file %s", path)


@router.post("/stt", response_model=STTResponse)
def speech_to_text(file: UploadFile = File(...)) -> STTResponse:
    if file.content_type not in {"audio/wav", "audio/x-wav", "audio/wave"}:
        raise HTTPException(status_code=400, detail="File must be WAV audio.")

    text = _transcribe_wav(file)
    return STTResponse(text=text)


@router.post("/tts")
def text_to_speech(request: TTSRequest, background_tasks: BackgroundTasks) -> FileResponse:
    if not request.text.strip():
        raise HTTPException(status_code=400, detail="Text payload must not be empty.")

    with tempfile.NamedTemporaryFile(delete=False, suffix=".wav") as temp_file:
        temp_path = temp_file.name

    with engine_lock:
        try:
            engine.save_to_file(request.text, temp_path)
            engine.runAndWait()
        except Exception as exc:
            logger.exception("TTS generation failed.")
            _cleanup_file(temp_path)
            raise HTTPException(status_code=500, detail="Failed to generate speech audio.")

    background_tasks.add_task(_cleanup_file, temp_path)
    return FileResponse(path=temp_path, media_type="audio/wav", filename="response.wav")

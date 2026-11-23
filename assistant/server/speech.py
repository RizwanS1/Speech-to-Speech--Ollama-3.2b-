import io
import json
import logging
import os
import shutil
import subprocess
import tempfile
import threading
import time
import wave
from decimal import Decimal
from typing import Annotated

import pyttsx3
import vosk
import speech_recognition as sr
from fastapi import APIRouter, BackgroundTasks, Depends, File, Form, HTTPException, UploadFile
from fastapi.responses import FileResponse
from sqlalchemy.ext.asyncio import AsyncSession
from starlette.concurrency import run_in_threadpool

from assistant.server.auth import get_current_user
from assistant.server.chat import llm
from assistant.server.config import get_settings
from assistant.server.db import get_db
from assistant.server.models import (
    ChatMessage,
    SpeechToSpeechResponse,
    STTResponse,
    TTSRequest,
    User,
)
from assistant.server.rate_limit import rate_limit

logger = logging.getLogger(__name__)
router = APIRouter()

VOSK_MODEL_PATH = os.environ.get("VOSK_MODEL_PATH", "./models/vosk-model-small-en-us-0.15")
ESPEAK_EXECUTABLE = shutil.which("espeak-ng") or shutil.which("espeak")
vosk_model = None
if os.path.isdir(VOSK_MODEL_PATH):
    try:
        vosk_model = vosk.Model(VOSK_MODEL_PATH)
    except Exception as exc:
        logger.exception("Failed to initialize Vosk model from %s.", VOSK_MODEL_PATH)
        vosk_model = None
else:
    logger.warning("Vosk model directory not found: %s. STT endpoint will be unavailable.", VOSK_MODEL_PATH)

engine = pyttsx3.init() if ESPEAK_EXECUTABLE is None else None
engine_lock = threading.Lock()

if engine is not None:
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


def _synthesize_wav(text: str, path: str) -> None:
    if ESPEAK_EXECUTABLE is not None:
        subprocess.run(
            [ESPEAK_EXECUTABLE, "-w", path, "-s", "170", "--stdin"],
            input=text,
            check=True,
            capture_output=True,
            encoding="utf-8",
            timeout=60,
        )
    else:
        if engine is None:
            raise RuntimeError("No text-to-speech engine is available.")
        with engine_lock:
            engine.save_to_file(text, path)
            engine.runAndWait()

    if os.path.getsize(path) <= 44:
        raise RuntimeError("Text-to-speech engine produced an empty WAV file.")
    with wave.open(path, "rb") as wav_file:
        if wav_file.getnframes() == 0:
            raise RuntimeError("Text-to-speech engine produced an empty WAV file.")


@router.post("/stt", response_model=STTResponse)
def speech_to_text(file: UploadFile = File(...)) -> STTResponse:
    if file.content_type not in {"audio/wav", "audio/x-wav", "audio/wave"}:
        raise HTTPException(status_code=400, detail="File must be WAV audio.")

    text = _transcribe_wav(file)
    return STTResponse(text=text)


@router.post(
    "/speech-to-speech",
    response_model=SpeechToSpeechResponse,
)
async def speech_to_speech(
    file: Annotated[UploadFile, File(...)],
    session_id: Annotated[str, Form(min_length=1, max_length=128)],
    current_user: Annotated[User, Depends(get_current_user)],
    _rate_limit: Annotated[
        None, Depends(rate_limit(max_requests=1, window_seconds=10, per_user=False))
    ],
    db: Annotated[AsyncSession, Depends(get_db)],
) -> SpeechToSpeechResponse:
    request_started_at = time.perf_counter()
    if file.content_type not in {"audio/wav", "audio/x-wav", "audio/wave"}:
        raise HTTPException(status_code=400, detail="File must be WAV audio.")

    transcript = await run_in_threadpool(_transcribe_wav, file)
    if not transcript.strip():
        return SpeechToSpeechResponse(
            session_id=session_id,
            transcript="",
            reply="",
            server_latency_ms=(time.perf_counter() - request_started_at) * 1000,
        )
    if llm is None:
        raise HTTPException(status_code=503, detail="Chat model is unavailable.")

    try:
        result = await run_in_threadpool(llm.generate, [transcript])
    except Exception as exc:
        logger.exception("Speech-to-speech chat generation failed.")
        raise HTTPException(status_code=503, detail="Chat response generation failed.") from exc

    generation = result.generations[0][0]
    reply = generation.text.strip()
    generation_info = generation.generation_info or {}
    prompt_tokens = generation_info.get("prompt_eval_count")
    completion_tokens = generation_info.get("eval_count")
    settings = get_settings()
    total_tokens = (
        prompt_tokens + completion_tokens
        if isinstance(prompt_tokens, int) and isinstance(completion_tokens, int)
        else None
    )
    estimated_cost_usd = None
    if isinstance(prompt_tokens, int) and isinstance(completion_tokens, int):
        estimated_cost_usd = float(
            (
                Decimal(prompt_tokens)
                * Decimal(str(settings.prompt_cost_per_million_tokens_usd))
                + Decimal(completion_tokens)
                * Decimal(str(settings.completion_cost_per_million_tokens_usd))
            )
            / Decimal(1_000_000)
        )
    db.add_all(
        [
            ChatMessage(
                user_id=current_user.id,
                session_id=session_id,
                role="user",
                content=transcript,
            ),
            ChatMessage(
                user_id=current_user.id,
                session_id=session_id,
                role="assistant",
                content=reply,
            ),
        ]
    )
    await db.commit()
    return SpeechToSpeechResponse(
        session_id=session_id,
        transcript=transcript,
        reply=reply,
        prompt_tokens=prompt_tokens if isinstance(prompt_tokens, int) else None,
        completion_tokens=completion_tokens if isinstance(completion_tokens, int) else None,
        total_tokens=total_tokens,
        estimated_cost_usd=estimated_cost_usd,
        server_latency_ms=(time.perf_counter() - request_started_at) * 1000,
        ollama_latency_ms=(
            generation_info["total_duration"] / 1_000_000
            if isinstance(generation_info.get("total_duration"), int)
            else None
        ),
        prompt_eval_latency_ms=(
            generation_info["prompt_eval_duration"] / 1_000_000
            if isinstance(generation_info.get("prompt_eval_duration"), int)
            else None
        ),
        generation_latency_ms=(
            generation_info["eval_duration"] / 1_000_000
            if isinstance(generation_info.get("eval_duration"), int)
            else None
        ),
    )


@router.post("/tts")
def text_to_speech(request: TTSRequest, background_tasks: BackgroundTasks) -> FileResponse:
    if not request.text.strip():
        raise HTTPException(status_code=400, detail="Text payload must not be empty.")

    with tempfile.NamedTemporaryFile(delete=False, suffix=".wav") as temp_file:
        temp_path = temp_file.name

    try:
        _synthesize_wav(request.text, temp_path)
    except (OSError, RuntimeError, subprocess.SubprocessError, wave.Error) as exc:
        logger.exception("TTS generation failed.")
        _cleanup_file(temp_path)
        raise HTTPException(status_code=500, detail="Failed to generate speech audio.") from exc

    background_tasks.add_task(_cleanup_file, temp_path)
    return FileResponse(path=temp_path, media_type="audio/wav", filename="response.wav")

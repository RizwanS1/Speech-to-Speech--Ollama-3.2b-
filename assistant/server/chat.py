import logging

from fastapi import APIRouter, HTTPException
from langchain_ollama import OllamaLLM

from assistant.server.models import ChatRequest, ChatResponse

logger = logging.getLogger(__name__)
router = APIRouter()

try:
    llm = OllamaLLM(model="llama3.2")
except Exception as exc:
    logger.exception("Failed to initialize Ollama LLM.")
    llm = None


@router.post("/", response_model=ChatResponse)
def chat_endpoint(request: ChatRequest) -> ChatResponse:
    if llm is None:
        logger.warning("Chat model is unavailable; returning fallback response.")
        return ChatResponse(reply="Sorry, the chat model is unavailable. Please start the Ollama server or set the model path and try again.")

    try:
        result = llm.invoke(input=request.message)
        reply_text = str(result).strip()
        return ChatResponse(reply=reply_text)
    except Exception as exc:
        logger.exception("Chat request failed.")
        return ChatResponse(reply="Sorry, I could not generate a chat response at this time.")

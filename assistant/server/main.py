import os

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import RedirectResponse
from fastapi.staticfiles import StaticFiles
from assistant.server.chat import router as chat_router
from assistant.server.speech import router as speech_router
from assistant.server.vision import router as vision_router

app = FastAPI(title="AI Voice Assistant Server")

app.add_middleware(
    CORSMiddleware,
    allow_origins=["http://127.0.0.1:8000", "http://localhost:8000"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

app.include_router(chat_router, prefix="/chat", tags=["chat"])
app.include_router(speech_router, prefix="/speech", tags=["speech"])
app.include_router(vision_router, prefix="/vision", tags=["vision"])

static_path = os.path.join(os.path.dirname(__file__), "static")
app.mount("/static", StaticFiles(directory=static_path), name="static")

@app.get("/")
def root() -> RedirectResponse:
    return RedirectResponse(url="/static/index.html")

@app.get("/health")
def health() -> dict:
    return {"status": "ok", "message": "AI Voice Assistant server is running."}

@app.get("/ui")
def web_ui() -> RedirectResponse:
    return RedirectResponse(url="/static/index.html")


if __name__ == "__main__":
    import uvicorn

    uvicorn.run(app, host="127.0.0.1", port=8000, log_level="info")

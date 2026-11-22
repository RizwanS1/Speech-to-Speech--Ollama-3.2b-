import os
from contextlib import asynccontextmanager
from collections.abc import AsyncIterator

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import RedirectResponse
from fastapi.staticfiles import StaticFiles
from redis.asyncio import Redis

from assistant.server.auth import router as auth_router
from assistant.server.config import get_settings
from assistant.server.db import close_database, configure_database, initialize_database
from assistant.server.chat import router as chat_router
from assistant.server.history import router as history_router
from assistant.server.speech import router as speech_router
from assistant.server.vision import router as vision_router


@asynccontextmanager
async def lifespan(app: FastAPI) -> AsyncIterator[None]:
    settings = get_settings()
    engine = configure_database()
    redis_client: Redis = Redis.from_url(
        settings.redis_url,
        encoding="utf-8",
        decode_responses=True,
    )
    app.state.redis = redis_client
    try:
        await initialize_database(engine)
        await redis_client.ping()
        yield
    finally:
        await redis_client.aclose()
        await close_database()


app = FastAPI(title="AI Voice Assistant Server", lifespan=lifespan)

# Configure CORS origins. For local development include the common frontend host/ports.
default_origins = [
    "http://127.0.0.1:8000",
    "http://localhost:8000",
    "http://127.0.0.1:8080",
    "http://localhost:8080",
    "http://127.0.0.1:8081",
    "http://localhost:8081",
]

# Optionally override with a comma-separated ALLOW_ORIGINS env var (useful for CI/deploy).
allow_origins_env = os.environ.get("ALLOW_ORIGINS")
if allow_origins_env:
    allow_origins = [o.strip() for o in allow_origins_env.split(",") if o.strip()]
else:
    allow_origins = default_origins

# For local development allow all origins to avoid CORS issues between container and host.
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=False,
    allow_methods=["*"],
    allow_headers=["*"],
)


# Debug fallback: ensure responses include Access-Control-Allow-Origin so browsers can reach the API
@app.middleware("http")
async def add_cors_header(request, call_next):
    response = await call_next(request)
    # Only add minimal permissive CORS headers for local debugging
    response.headers["Access-Control-Allow-Origin"] = "*"
    response.headers["Access-Control-Allow-Methods"] = "GET,POST,OPTIONS,PUT,PATCH,DELETE"
    response.headers["Access-Control-Allow-Headers"] = "*"
    return response

app.include_router(chat_router, prefix="/chat", tags=["chat"])
app.include_router(speech_router, prefix="/speech", tags=["speech"])
app.include_router(vision_router, prefix="/vision", tags=["vision"])
app.include_router(auth_router)
app.include_router(history_router)

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

import os
import math
from dataclasses import dataclass

from dotenv import load_dotenv

load_dotenv()

DEFAULT_CORS_ORIGINS = (
    "http://localhost:4566",
    "http://127.0.0.1:4566",
    "http://localhost:8000",
)


@dataclass(frozen=True)
class Settings:
    database_url: str
    redis_url: str
    jwt_secret: str
    jwt_algorithm: str
    access_token_expire_minutes: int
    prompt_cost_per_million_tokens_usd: float
    completion_cost_per_million_tokens_usd: float
    cors_origins: list[str]
    ollama_url: str


def get_cors_origins() -> list[str]:
    configured_origins = os.getenv("CORS_ORIGINS")
    if configured_origins is None:
        return list(DEFAULT_CORS_ORIGINS)

    origins = [origin.strip() for origin in configured_origins.split(",") if origin.strip()]
    if not origins:
        raise RuntimeError("CORS_ORIGINS must contain at least one origin.")
    return origins


def get_ollama_url() -> str:
    ollama_url = os.getenv("OLLAMA_URL", "http://localhost:11434").strip().rstrip("/")
    if not ollama_url.startswith(("http://", "https://")):
        raise RuntimeError("OLLAMA_URL must be an HTTP or HTTPS URL.")
    return ollama_url


def get_ollama_model() -> str:
    model = os.getenv("OLLAMA_MODEL", "llama3.2").strip()
    if not model:
        raise RuntimeError("OLLAMA_MODEL must be set.")
    return model


def _read_nonnegative_rate(name: str) -> float:
    value = os.getenv(name, "0").strip()
    try:
        rate = float(value)
    except ValueError as exc:
        raise RuntimeError(f"{name} must be a non-negative number.") from exc
    if not math.isfinite(rate) or rate < 0:
        raise RuntimeError(f"{name} must be a non-negative number.")
    return rate


def get_settings() -> Settings:
    database_url = os.getenv("DATABASE_URL", "").strip()
    if database_url.startswith("postgresql://"):
        database_url = database_url.replace(
            "postgresql://", "postgresql+asyncpg://", 1
        )
    redis_url = os.getenv("REDIS_URL", "").strip()
    jwt_secret = os.getenv("JWT_SECRET") or os.getenv("JWT_SECRET_KEY", "")
    jwt_algorithm = os.getenv("JWT_ALGORITHM", "HS256").strip()

    if not database_url:
        raise RuntimeError("DATABASE_URL must be set.")
    if not database_url.startswith("postgresql+asyncpg://"):
        raise RuntimeError("DATABASE_URL must use the postgresql+asyncpg:// scheme.")
    if not redis_url:
        raise RuntimeError("REDIS_URL must be set.")
    if len(jwt_secret.encode("utf-8")) < 32:
        raise RuntimeError("JWT_SECRET must be at least 32 bytes.")
    if jwt_algorithm not in {"HS256", "HS384", "HS512"}:
        raise RuntimeError("JWT_ALGORITHM must be one of HS256, HS384, or HS512.")

    try:
        access_token_expire_minutes = int(os.getenv("ACCESS_TOKEN_EXPIRE_MINUTES", "30"))
    except ValueError as exc:
        raise RuntimeError("ACCESS_TOKEN_EXPIRE_MINUTES must be a positive integer.") from exc
    if access_token_expire_minutes <= 0:
        raise RuntimeError("ACCESS_TOKEN_EXPIRE_MINUTES must be a positive integer.")

    return Settings(
        database_url=database_url,
        redis_url=redis_url,
        jwt_secret=jwt_secret,
        jwt_algorithm=jwt_algorithm,
        access_token_expire_minutes=access_token_expire_minutes,
        prompt_cost_per_million_tokens_usd=_read_nonnegative_rate(
            "PROMPT_COST_PER_MILLION_TOKENS_USD"
        ),
        completion_cost_per_million_tokens_usd=_read_nonnegative_rate(
            "COMPLETION_COST_PER_MILLION_TOKENS_USD"
        ),
        cors_origins=get_cors_origins(),
        ollama_url=get_ollama_url(),
    )

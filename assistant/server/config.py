import os
import math
from dataclasses import dataclass

from dotenv import load_dotenv

load_dotenv()


@dataclass(frozen=True)
class Settings:
    database_url: str
    redis_url: str
    jwt_secret: str
    jwt_algorithm: str
    access_token_expire_minutes: int
    prompt_cost_per_million_tokens_usd: float
    completion_cost_per_million_tokens_usd: float


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
    redis_url = os.getenv("REDIS_URL", "").strip()
    jwt_secret = os.getenv("JWT_SECRET", "")
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
    )

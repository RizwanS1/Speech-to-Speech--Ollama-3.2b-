import logging
from collections.abc import Awaitable, Callable

from fastapi import HTTPException, Request, status
from redis.asyncio import Redis
from redis.exceptions import RedisError

logger = logging.getLogger(__name__)


def rate_limit(
    max_requests: int,
    window_seconds: int,
    *,
    per_user: bool = True,
) -> Callable[..., Awaitable[None]]:
    if max_requests < 1 or window_seconds < 1:
        raise ValueError("Rate-limit values must be positive integers.")

    async def enforce_rate_limit(request: Request) -> None:
        redis: Redis = request.app.state.redis
        user_id = getattr(request.state, "user_id", None)
        if per_user and user_id is not None:
            identity = str(user_id)
        else:
            identity = request.client.host if request.client is not None else "unknown"

        key = f"ratelimit:{identity}:{request.url.path}"
        try:
            async with redis.pipeline(transaction=True) as pipeline:
                pipeline.set(key, 0, nx=True, ex=window_seconds)
                pipeline.incr(key)
                results = await pipeline.execute()

            request_count = int(results[1])
            if request_count > max_requests:
                retry_after = await redis.ttl(key)
                raise HTTPException(
                    status_code=status.HTTP_429_TOO_MANY_REQUESTS,
                    detail="Rate limit exceeded.",
                    headers={"Retry-After": str(max(retry_after, 1))},
                )
        except RedisError as exc:
            logger.exception("Redis rate limiting failed.")
            raise HTTPException(
                status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
                detail="Rate limiting service unavailable.",
            ) from exc

    return enforce_rate_limit

from fastapi import HTTPException


async def check_rate_limit(
    redis, family_id: int, action: str, max_requests: int, window_seconds: int
) -> None:
    """Check rate limit using a simple Redis counter with expiry.

    Raises HTTP 429 if the limit is exceeded.
    """
    key = f"rate:{action}:{family_id}"
    current = await redis.incr(key)
    if current == 1:
        await redis.expire(key, window_seconds)
    if current > max_requests:
        raise HTTPException(
            status_code=429,
            detail=f"Rate limit exceeded for {action}. Try again later.",
        )

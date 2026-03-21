from fastapi import HTTPException, Request

# Atomic Lua script: increments counter and sets TTL in one round-trip.
# Avoids the race condition where INCR succeeds but EXPIRE never runs.
_RATE_LIMIT_SCRIPT = """
local current = redis.call('INCR', KEYS[1])
if current == 1 then
    redis.call('EXPIRE', KEYS[1], ARGV[1])
end
return current
"""


async def check_rate_limit(
    redis, family_id: int, action: str, max_requests: int, window_seconds: int
) -> None:
    """Check rate limit using an atomic Redis counter with expiry.

    Raises HTTP 429 if the limit is exceeded.
    """
    key = f"rate:{action}:{family_id}"
    current = await redis.eval(_RATE_LIMIT_SCRIPT, 1, key, window_seconds)
    if current > max_requests:
        raise HTTPException(
            status_code=429,
            detail=f"Rate limit exceeded for {action}. Try again later.",
        )


def _get_client_ip(request: Request) -> str:
    """Extract client IP from request, respecting X-Forwarded-For."""
    forwarded = request.headers.get("x-forwarded-for")
    if forwarded:
        return forwarded.split(",")[0].strip()
    return request.client.host if request.client else "unknown"


async def check_rate_limit_by_ip(
    redis, request: Request, action: str, max_requests: int, window_seconds: int
) -> None:
    """Rate limit by client IP for unauthenticated endpoints."""
    ip = _get_client_ip(request)
    key = f"rate:{action}:ip:{ip}"
    current = await redis.eval(_RATE_LIMIT_SCRIPT, 1, key, window_seconds)
    if current > max_requests:
        raise HTTPException(
            status_code=429,
            detail="Too many requests. Try again later.",
        )

import uuid
from datetime import datetime, timedelta, timezone

from fastapi import Depends, HTTPException, Request
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer
from jose import JWTError, jwt
from passlib.context import CryptContext

from config import settings

pwd_context = CryptContext(schemes=["bcrypt"], deprecated="auto")
security = HTTPBearer()

REFRESH_TOKEN_PREFIX = "refresh_token:"


def hash_password(password: str) -> str:
    return pwd_context.hash(password)


def verify_password(plain: str, hashed: str) -> bool:
    return pwd_context.verify(plain, hashed)


def create_access_token(family_id: int) -> str:
    expire = datetime.now(timezone.utc) + timedelta(minutes=settings.JWT_ACCESS_EXPIRES_MINUTES)
    return jwt.encode(
        {"sub": str(family_id), "exp": expire, "type": "access"},
        settings.JWT_SECRET,
        algorithm="HS256",
    )


def create_refresh_token(family_id: int) -> str:
    jti = str(uuid.uuid4())
    expire = datetime.now(timezone.utc) + timedelta(days=settings.JWT_REFRESH_EXPIRES_DAYS)
    return jwt.encode(
        {"sub": str(family_id), "exp": expire, "type": "refresh", "jti": jti},
        settings.JWT_SECRET,
        algorithm="HS256",
    )


async def store_refresh_token(redis, token: str, family_id: int) -> None:
    """Store a refresh token in Redis so it can be revoked later."""
    try:
        payload = jwt.decode(token, settings.JWT_SECRET, algorithms=["HS256"])
        jti = payload.get("jti")
        if jti:
            ttl = settings.JWT_REFRESH_EXPIRES_DAYS * 86400
            await redis.setex(f"{REFRESH_TOKEN_PREFIX}{jti}", ttl, str(family_id))
    except JWTError:
        pass


async def is_refresh_token_valid(redis, token: str) -> bool:
    """Check if a refresh token has not been revoked."""
    try:
        payload = jwt.decode(token, settings.JWT_SECRET, algorithms=["HS256"])
        jti = payload.get("jti")
        if not jti:
            return False
        return await redis.exists(f"{REFRESH_TOKEN_PREFIX}{jti}") == 1
    except JWTError:
        return False


async def revoke_refresh_token(redis, token: str) -> None:
    """Revoke a specific refresh token."""
    try:
        payload = jwt.decode(token, settings.JWT_SECRET, algorithms=["HS256"])
        jti = payload.get("jti")
        if jti:
            await redis.delete(f"{REFRESH_TOKEN_PREFIX}{jti}")
    except JWTError:
        pass


async def revoke_all_family_tokens(redis, family_id: int) -> None:
    """Revoke all refresh tokens for a family by scanning Redis keys."""
    cursor = b"0"
    while True:
        cursor, keys = await redis.scan(
            cursor=cursor, match=f"{REFRESH_TOKEN_PREFIX}*", count=100
        )
        for key in keys:
            val = await redis.get(key)
            if val and val.decode() == str(family_id):
                await redis.delete(key)
        if cursor == b"0":
            break


async def get_current_family(
    credentials: HTTPAuthorizationCredentials = Depends(security),
) -> int:
    """FastAPI dependency that decodes a JWT and returns the family_id."""
    try:
        payload = jwt.decode(
            credentials.credentials, settings.JWT_SECRET, algorithms=["HS256"]
        )
        if payload.get("type") != "access":
            raise HTTPException(status_code=401, detail="Invalid token type")
        return int(payload["sub"])
    except (JWTError, ValueError, KeyError):
        raise HTTPException(status_code=401, detail="Invalid or expired token")

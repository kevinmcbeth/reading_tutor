from datetime import datetime, timedelta

from fastapi import Depends, HTTPException
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer
from jose import JWTError, jwt
from passlib.context import CryptContext

from config import settings

pwd_context = CryptContext(schemes=["bcrypt"], deprecated="auto")
security = HTTPBearer()


def hash_password(password: str) -> str:
    return pwd_context.hash(password)


def verify_password(plain: str, hashed: str) -> bool:
    return pwd_context.verify(plain, hashed)


def create_access_token(family_id: int) -> str:
    expire = datetime.utcnow() + timedelta(minutes=settings.JWT_ACCESS_EXPIRES_MINUTES)
    return jwt.encode(
        {"sub": str(family_id), "exp": expire, "type": "access"},
        settings.JWT_SECRET,
        algorithm="HS256",
    )


def create_refresh_token(family_id: int) -> str:
    expire = datetime.utcnow() + timedelta(days=settings.JWT_REFRESH_EXPIRES_DAYS)
    return jwt.encode(
        {"sub": str(family_id), "exp": expire, "type": "refresh"},
        settings.JWT_SECRET,
        algorithm="HS256",
    )


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

import uuid
from dataclasses import dataclass
from datetime import datetime, timedelta, timezone

import jwt
from passlib.context import CryptContext

from src.config import settings

pwd_context = CryptContext(schemes=["bcrypt"], deprecated="auto")


def hash_password(password: str) -> str:
    return pwd_context.hash(password)


def verify_password(plain_password: str, hashed_password: str) -> bool:
    return pwd_context.verify(plain_password, hashed_password)


@dataclass
class DecodedToken:
    user_id: uuid.UUID
    token_version: int


def create_access_token(user_id: uuid.UUID, token_version: int) -> str:
    expire = datetime.now(timezone.utc) + timedelta(minutes=settings.ACCESS_TOKEN_EXPIRE_MINUTES)
    # tv lets get_current_user notice a password reset that happened AFTER
    # this token was issued and reject it outright, even though it's still
    # cryptographically valid and unexpired - see User.token_version.
    payload = {"sub": str(user_id), "exp": expire, "tv": token_version}
    return jwt.encode(payload, settings.JWT_SECRET_KEY, algorithm=settings.JWT_ALGORITHM)


def decode_access_token(token: str) -> DecodedToken | None:
    try:
        payload = jwt.decode(token, settings.JWT_SECRET_KEY, algorithms=[settings.JWT_ALGORITHM])
        return DecodedToken(user_id=uuid.UUID(payload["sub"]), token_version=payload["tv"])
    except (jwt.PyJWTError, KeyError, ValueError):
        return None

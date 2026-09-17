from fastapi import Depends, HTTPException, status
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer
from sqlmodel.ext.asyncio.session import AsyncSession

from src.auth.models import User
from src.auth.utils import decode_access_token
from src.db.main import get_session

bearer_scheme = HTTPBearer()


async def get_current_user(
    credentials: HTTPAuthorizationCredentials = Depends(bearer_scheme),
    session: AsyncSession = Depends(get_session),
) -> User:
    unauthorized = HTTPException(
        status_code=status.HTTP_401_UNAUTHORIZED,
        detail="Could not validate credentials",
        headers={"WWW-Authenticate": "Bearer"},
    )

    decoded = decode_access_token(credentials.credentials)
    if decoded is None:
        raise unauthorized

    user = await session.get(User, decoded.user_id)
    if user is None or not user.is_active or user.closed_at is not None:
        raise unauthorized

    # A password reset bumps User.token_version (see confirm_password_reset)
    # - any token minted against an older version is rejected here even
    # though it's still cryptographically valid and unexpired, so a reset
    # actually revokes every session it should.
    if decoded.token_version != user.token_version:
        raise unauthorized

    return user


async def get_current_admin(current_user: User = Depends(get_current_user)) -> User:
    if not current_user.is_admin:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Admin access required")
    return current_user

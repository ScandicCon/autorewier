from fastapi import Cookie, Depends, Header, HTTPException, Request
from sqlalchemy.ext.asyncio import AsyncSession

from app.config import settings
from app.database import get_db
from app.models import User
from app.services.auth import COOKIE_NAME, decode_jwt, get_user_by_session
from app.services.inspections import get_or_create_user


async def get_current_user(
    request: Request,
    session: AsyncSession = Depends(get_db),
    x_telegram_id: int | None = Header(None, alias="X-Telegram-Id"),
    x_telegram_secret: str | None = Header(None, alias="X-Telegram-Secret"),
    authorization: str | None = Header(None),
    autorewier_session: str | None = Cookie(None, alias=COOKIE_NAME),
) -> User:
    if settings.enable_telegram_header_auth and x_telegram_id is not None:
        if settings.telegram_header_secret and x_telegram_secret != settings.telegram_header_secret:
            raise HTTPException(401, "Invalid telegram auth secret")
        if settings.is_production and not settings.telegram_header_secret:
            raise HTTPException(401, "Telegram header auth secret is required in production")
        return await get_or_create_user(session, x_telegram_id)

    if autorewier_session:
        user = await get_user_by_session(session, autorewier_session)
        if user:
            return user

    if authorization and authorization.startswith("Bearer "):
        payload = decode_jwt(authorization[7:])
        if payload and payload.get("sub"):
            from app.services.auth import get_user_by_id

            user = await get_user_by_id(session, int(payload["sub"]))
            if user:
                return user

    raise HTTPException(401, "Требуется авторизация")


async def get_user_id(user: User = Depends(get_current_user)) -> int:
    return user.id

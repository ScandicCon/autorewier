import secrets
import uuid
from datetime import datetime, timedelta, timezone

import bcrypt
import jwt
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.config import settings
from app.models import User
from app.services.verification_delivery import get_verification_email_provider

ALGORITHM = "HS256"
COOKIE_NAME = "autorewier_session"
_BCRYPT_MAX = 72
VERIFICATION_COOLDOWN_SECONDS = 60
PASSWORD_RESET_TOKEN_TTL_HOURS = 1


def _now_utc() -> datetime:
    return datetime.now(timezone.utc).replace(tzinfo=None)


def session_ttl() -> timedelta:
    return timedelta(seconds=max(300, settings.web_session_ttl_seconds))


def session_cookie_kwargs() -> dict:
    kwargs = {
        "httponly": True,
        "max_age": int(session_ttl().total_seconds()),
        "samesite": settings.effective_cookie_samesite,
        "secure": settings.effective_cookie_secure,
        "path": "/",
    }
    if settings.web_cookie_domain.strip():
        kwargs["domain"] = settings.web_cookie_domain.strip()
    return kwargs


def _password_bytes(password: str) -> bytes:
    return password.encode("utf-8")[:_BCRYPT_MAX]


def hash_password(password: str) -> str:
    return bcrypt.hashpw(_password_bytes(password), bcrypt.gensalt()).decode("utf-8")


def verify_password(password: str, password_hash: str) -> bool:
    try:
        return bcrypt.checkpw(
            _password_bytes(password),
            password_hash.encode("utf-8"),
        )
    except (ValueError, TypeError):
        return False


def create_jwt(user_id: int, email: str) -> str:
    now = _now_utc()
    expire = now + session_ttl()
    payload = {"sub": str(user_id), "email": email, "iat": now, "exp": expire}
    return jwt.encode(payload, settings.web_secret_key, algorithm=ALGORITHM)


def decode_jwt(token: str) -> dict | None:
    try:
        return jwt.decode(token, settings.web_secret_key, algorithms=[ALGORITHM])
    except jwt.PyJWTError:
        return None


def new_session_token() -> str:
    return secrets.token_urlsafe(32)


def _generate_otp_code() -> str:
    return f"{secrets.randbelow(10**6):06d}"


def _mask_email(email: str | None) -> str | None:
    if not email or "@" not in email:
        return None
    local, domain = email.split("@", 1)
    if len(local) <= 2:
        masked_local = local[0] + "*"
    else:
        masked_local = local[:2] + "*" * max(1, len(local) - 2)
    return f"{masked_local}@{domain}"


def _mask_phone(phone: str | None) -> str | None:
    if not phone:
        return None
    digits = "".join(ch for ch in phone if ch.isdigit())
    if len(digits) < 4:
        return None
    return f"+*** *** ** {digits[-2:]}"


def issue_session(user: User) -> None:
    now = _now_utc()
    user.session_token = new_session_token()
    user.session_issued_at = now
    user.session_expires_at = now + session_ttl()


async def register_user(
    session: AsyncSession, email: str, password: str
) -> User:
    email = email.strip().lower()
    if "@" not in email:
        raise ValueError("Укажите корректный email (например user@mail.ru)")
    if len(password) < 6:
        raise ValueError("Пароль должен быть не короче 6 символов")
    existing = await session.execute(select(User).where(User.email == email))
    if existing.scalar_one_or_none():
        raise ValueError("Email уже зарегистрирован")
    user = User(
        email=email,
        password_hash=hash_password(password),
        email_verified=False,
    )
    issue_session(user)
    session.add(user)
    await session.commit()
    await session.refresh(user)
    return user


async def authenticate_user(
    session: AsyncSession, email: str, password: str
) -> User | None:
    email = email.strip().lower()
    result = await session.execute(select(User).where(User.email == email))
    user = result.scalar_one_or_none()
    if not user or not user.password_hash:
        return None
    if not verify_password(password, user.password_hash):
        return None
    issue_session(user)
    await session.commit()
    await session.refresh(user)
    return user


async def get_user_by_session(
    session: AsyncSession, session_token: str | None
) -> User | None:
    if not session_token:
        return None
    result = await session.execute(
        select(User).where(User.session_token == session_token)
    )
    user = result.scalar_one_or_none()
    if not user:
        return None
    if user.session_expires_at and user.session_expires_at < _now_utc():
        return None
    return user


async def get_user_by_id(session: AsyncSession, user_id: int) -> User | None:
    result = await session.execute(select(User).where(User.id == user_id))
    return result.scalar_one_or_none()


async def issue_verification_code(
    session: AsyncSession,
    user: User,
    *,
    channel: str = "email",
    email: str | None = None,
    phone_number: str | None = None,
) -> dict:
    now = _now_utc()
    ttl = timedelta(minutes=max(3, settings.verification_code_ttl_minutes))

    # Cooldown: not more than once per 60 seconds
    if user.email_verification_sent_at is not None:
        elapsed = (now - user.email_verification_sent_at).total_seconds()
        if elapsed < VERIFICATION_COOLDOWN_SECONDS:
            wait = int(VERIFICATION_COOLDOWN_SECONDS - elapsed)
            raise ValueError(
                f"Подождите {wait} сек. перед повторной отправкой кода."
            )

    code = _generate_otp_code()
    delivered = False
    message = "Код создан."
    resolved_channel = channel.lower().strip()
    if resolved_channel not in {"email", "phone"}:
        resolved_channel = "email"

    if resolved_channel == "phone":
        if phone_number:
            user.phone_number = phone_number.strip()
        user.phone_verified = False
        user.email_verification_code = code
        user.email_verification_expires_at = now + ttl
        delivered = False
        message = "SMS-шлюз не подключен. Используйте email-подтверждение или подключите SMS провайдера."
    else:
        target_email = (email or user.email or "").strip().lower()
        if not target_email:
            raise ValueError("Email обязателен для подтверждения.")
        user.email = target_email
        user.email_verified = False
        user.email_verification_code = code
        user.email_verification_expires_at = now + ttl
        user.email_verification_sent_at = now
        provider = get_verification_email_provider()
        delivery = await provider.send_code(target_email, code)
        delivered = delivery.delivered
        if delivered:
            message = delivery.message
            if delivery.dev_code:
                message = f"{delivery.message} Код для теста: {delivery.dev_code}"
        else:
            # Delivery failed — log it but don't crash: the code is saved in DB,
            # the user can still enter it manually if they receive the email later.
            import logging
            logging.getLogger("autorewier.smtp").error(
                "Verification email delivery failed (provider=%s): %s",
                delivery.provider, delivery.message,
            )
            if settings.is_production:
                raise ValueError(
                    "Не удалось отправить письмо подтверждения: в production "
                    f"требуется настроенный SMTP/провайдер почты. {delivery.message}"
                )
            message = f"Не удалось отправить письмо: {delivery.message}"

    await session.commit()
    await session.refresh(user)
    return {
        "ok": True,
        "channel": resolved_channel,
        "delivered": delivered,
        "message": message,
        "email_masked": _mask_email(user.email),
        "phone_masked": _mask_phone(user.phone_number),
    }


async def confirm_verification_code(
    session: AsyncSession,
    user: User,
    *,
    code: str,
    channel: str = "email",
) -> dict:
    now = _now_utc()
    expected = (user.email_verification_code or "").strip()
    expires_at = user.email_verification_expires_at
    if not expected:
        raise ValueError("Код подтверждения не запрошен.")
    if not expires_at or expires_at < now:
        raise ValueError("Срок действия кода истек. Запросите новый код.")
    if expected != code.strip():
        raise ValueError("Неверный код подтверждения.")

    resolved_channel = channel.lower().strip()
    if resolved_channel == "phone":
        user.phone_verified = True
    else:
        user.email_verified = True
    user.email_verification_code = None
    user.email_verification_expires_at = None
    await session.commit()
    await session.refresh(user)
    return {
        "ok": True,
        "channel": resolved_channel if resolved_channel in {"email", "phone"} else "email",
        "email_verified": bool(user.email_verified),
        "phone_verified": bool(user.phone_verified),
        "email_masked": _mask_email(user.email),
        "phone_masked": _mask_phone(user.phone_number),
    }


async def issue_password_reset(
    session: AsyncSession,
    email: str,
) -> dict:
    import logging
    logger = logging.getLogger("autorewier.auth")

    email = email.strip().lower()
    result = await session.execute(select(User).where(User.email == email))
    user = result.scalar_one_or_none()

    if not user:
        return {"ok": True, "message": "Если аккаунт существует, письмо отправлено."}

    now = _now_utc()
    token = str(uuid.uuid4())
    user.password_reset_token = token
    user.password_reset_expires_at = now + timedelta(hours=PASSWORD_RESET_TOKEN_TTL_HOURS)
    await session.commit()

    reset_link = f"{settings.web_base_url}/reset-password?token={token}"

    provider = get_verification_email_provider()
    try:
        delivery = await provider.send_reset_link(email, reset_link)
        if not delivery.delivered:
            logger.info(
                "password_reset_link_dev",
                extra={"email": _mask_email(email), "link": reset_link},
            )
    except AttributeError:
        logger.info(
            "password_reset_link_dev",
            extra={"email": _mask_email(email), "link": reset_link},
        )
    except Exception as exc:
        logger.warning(
            "password_reset_send_failed",
            extra={"email": _mask_email(email), "error": str(exc)},
        )

    return {"ok": True, "message": "Если аккаунт существует, письмо отправлено."}


async def reset_password(
    session: AsyncSession,
    token: str,
    new_password: str,
) -> dict:
    if len(new_password) < 6:
        raise ValueError("Пароль должен быть не короче 6 символов")

    now = _now_utc()
    result = await session.execute(
        select(User).where(User.password_reset_token == token)
    )
    user = result.scalar_one_or_none()

    if not user:
        raise ValueError("Недействительный токен восстановления пароля.")
    if not user.password_reset_expires_at or user.password_reset_expires_at < now:
        raise ValueError("Токен истёк. Запросите новую ссылку восстановления.")

    user.password_hash = hash_password(new_password)
    user.password_reset_token = None
    user.password_reset_expires_at = None
    issue_session(user)
    await session.commit()
    await session.refresh(user)
    return {"ok": True, "message": "Пароль успешно изменён."}

import secrets

from fastapi import APIRouter, Depends, HTTPException, Request, Response
from fastapi.responses import RedirectResponse
from sqlalchemy.ext.asyncio import AsyncSession

from app.config import settings
from app.database import get_db
from app.deps import get_current_user
from app.models import User
from app.schemas import LoginRequest, RegisterRequest
from app.services.subscription import is_pro_active
from app.services import oauth as oauth_service
from app.security.rate_limit import enforce_rate_limit
from app.services.analytics import track_event
from app.services.auth import (
    COOKIE_NAME,
    authenticate_user,
    confirm_verification_code,
    create_jwt,
    issue_password_reset,
    issue_verification_code,
    register_user,
    reset_password,
    session_cookie_kwargs,
)
from app.schemas import (
    ForgotPasswordRequest,
    ResetPasswordRequest,
    VerificationConfirmRequest,
    VerificationRequest,
    VerificationStatusResponse,
)

router = APIRouter(prefix="/auth", tags=["auth"])


@router.post("/register")
async def register(
    body: RegisterRequest,
    request: Request,
    session: AsyncSession = Depends(get_db),
):
    await enforce_rate_limit(
        request,
        scope="auth_register",
        limit=settings.rate_limit_register_limit,
        window_seconds=settings.rate_limit_register_window_seconds,
    )
    try:
        user = await register_user(session, body.email, body.password)
    except ValueError as e:
        raise HTTPException(400, str(e)) from e
    await track_event("auth_register", user_id=user.id, props={"origin": "api"})
    return {
        "id": user.id,
        "email": user.email,
        "email_verified": bool(user.email_verified),
        "message": "Регистрация прошла успешно. Войдите в систему.",
    }


@router.post("/login")
async def login(
    body: LoginRequest,
    request: Request,
    response: Response,
    session: AsyncSession = Depends(get_db),
):
    await enforce_rate_limit(
        request,
        scope="auth_login",
        limit=settings.rate_limit_login_limit,
        window_seconds=settings.rate_limit_login_window_seconds,
    )
    user = await authenticate_user(session, body.email, body.password)
    if not user:
        raise HTTPException(401, "Неверный email или пароль")
    response.set_cookie(COOKIE_NAME, user.session_token, **session_cookie_kwargs())
    await track_event("auth_login", user_id=user.id, props={"origin": "api"})
    return {
        "id": user.id,
        "email": user.email,
        "plan": user.subscription_plan.value,
        "is_pro": is_pro_active(user),
        "email_verified": bool(user.email_verified),
        "token": create_jwt(user.id, user.email),
    }


@router.post("/logout")
async def logout(response: Response):
    kwargs = {"path": "/"}
    if settings.web_cookie_domain.strip():
        kwargs["domain"] = settings.web_cookie_domain.strip()
    response.delete_cookie(COOKIE_NAME, **kwargs)
    return {"message": "ok"}


@router.get("/check")
async def check_auth(user: User = Depends(get_current_user)):
    return {"authenticated": True, "email": user.email, "email_verified": user.email_verified}


@router.get("/me")
async def auth_me(user: User = Depends(get_current_user)):
    return {
        "id": user.id,
        "email": user.email,
        "email_verified": bool(user.email_verified),
        "phone_number": user.phone_number,
        "phone_verified": bool(user.phone_verified),
    }


@router.post("/forgot-password")
async def forgot_password(
    body: ForgotPasswordRequest,
    request: Request,
    session: AsyncSession = Depends(get_db),
):
    await enforce_rate_limit(
        request,
        scope="auth_forgot_password",
        limit=5,
        window_seconds=300,
    )
    result = await issue_password_reset(session, body.email)
    return result


@router.post("/reset-password")
async def reset_password_api(
    body: ResetPasswordRequest,
    session: AsyncSession = Depends(get_db),
):
    try:
        result = await reset_password(session, body.token, body.new_password)
    except ValueError as e:
        raise HTTPException(400, str(e)) from e
    return result


@router.post("/send-verification")
async def send_verification(
    body: VerificationRequest,
    request: Request,
    user: User = Depends(get_current_user),
    session: AsyncSession = Depends(get_db),
):
    await enforce_rate_limit(
        request,
        scope="auth_verification_request",
        limit=10,
        window_seconds=300,
        identity=str(user.id),
    )
    try:
        return await issue_verification_code(
            session,
            user,
            channel=body.channel,
            email=body.email,
            phone_number=body.phone_number,
        )
    except ValueError as e:
        raise HTTPException(400, str(e)) from e


@router.post("/verify-email", response_model=VerificationStatusResponse)
async def verify_email(
    body: VerificationConfirmRequest,
    request: Request,
    user: User = Depends(get_current_user),
    session: AsyncSession = Depends(get_db),
):
    await enforce_rate_limit(
        request,
        scope="auth_verification_confirm",
        limit=10,
        window_seconds=300,
        identity=str(user.id),
    )
    try:
        result = await confirm_verification_code(
            session, user, code=body.code, channel=body.channel
        )
    except ValueError as e:
        raise HTTPException(400, str(e)) from e
    return VerificationStatusResponse(
        email_verified=result["email_verified"],
        phone_verified=result["phone_verified"],
        email_masked=result["email_masked"],
        phone_masked=result["phone_masked"],
    )


@router.post("/verification/request")
async def request_verification(
    body: VerificationRequest,
    request: Request,
    user: User = Depends(get_current_user),
    session: AsyncSession = Depends(get_db),
):
    await enforce_rate_limit(
        request,
        scope="auth_verification_request",
        limit=10,
        window_seconds=300,
        identity=str(user.id),
    )
    try:
        return await issue_verification_code(
            session,
            user,
            channel=body.channel,
            email=body.email,
            phone_number=body.phone_number,
        )
    except ValueError as e:
        raise HTTPException(400, str(e)) from e


@router.post("/verification/confirm", response_model=VerificationStatusResponse)
async def confirm_verification(
    body: VerificationConfirmRequest,
    request: Request,
    user: User = Depends(get_current_user),
    session: AsyncSession = Depends(get_db),
):
    await enforce_rate_limit(
        request,
        scope="auth_verification_confirm",
        limit=10,
        window_seconds=300,
        identity=str(user.id),
    )
    try:
        result = await confirm_verification_code(
            session, user, code=body.code, channel=body.channel
        )
    except ValueError as e:
        raise HTTPException(400, str(e)) from e
    return VerificationStatusResponse(
        email_verified=result["email_verified"],
        phone_verified=result["phone_verified"],
        email_masked=result["email_masked"],
        phone_masked=result["phone_masked"],
    )


# ---------------------------------------------------------------------------
# Вход через соцсети (OAuth) + Telegram Login
# ---------------------------------------------------------------------------

@router.get("/oauth/providers")
async def oauth_providers():
    """Список включённых провайдеров соц-входа (для фронта)."""
    enabled = [p for p in oauth_service.REDIRECT_PROVIDERS if oauth_service.provider_enabled(p)]
    return {"providers": enabled, "telegram": oauth_service.provider_enabled("telegram")}


@router.get("/oauth/{provider}/start")
async def oauth_start(provider: str, request: Request):
    if not oauth_service.provider_enabled(provider) or provider not in oauth_service.REDIRECT_PROVIDERS:
        raise HTTPException(404, "Провайдер недоступен или не настроен")
    await enforce_rate_limit(request, scope="oauth_start", limit=20, window_seconds=300)
    state = secrets.token_urlsafe(16)
    return RedirectResponse(oauth_service.build_authorize_url(provider, state), status_code=307)


@router.get("/oauth/{provider}/callback")
async def oauth_callback(
    provider: str,
    request: Request,
    code: str | None = None,
    error: str | None = None,
    session: AsyncSession = Depends(get_db),
):
    redirect_base = oauth_service.success_redirect()
    if error or not code or not oauth_service.provider_enabled(provider):
        return RedirectResponse(f"{redirect_base}?error=oauth_failed", status_code=307)
    try:
        profile = await oauth_service.exchange_code(provider, code)
        user = await oauth_service.find_or_create_oauth_user(
            session,
            provider=profile["provider"],
            sub=profile["sub"],
            email=profile.get("email"),
            name=profile.get("name"),
        )
    except Exception:
        return RedirectResponse(f"{redirect_base}?error=oauth_failed", status_code=307)
    await track_event("oauth_login", user_id=user.id, props={"provider": provider})
    token = create_jwt(user.id, user.email)
    return RedirectResponse(f"{redirect_base}?token={token}", status_code=307)


@router.get("/telegram/callback")
async def telegram_callback(request: Request, session: AsyncSession = Depends(get_db)):
    """Приём данных Telegram Login Widget через data-auth-url (GET с параметрами)."""
    redirect_base = oauth_service.success_redirect()
    params = dict(request.query_params)
    if not oauth_service.provider_enabled("telegram") or not oauth_service.verify_telegram_auth(params):
        return RedirectResponse(f"{redirect_base}?error=telegram_failed", status_code=307)
    tg_id = params.get("id")
    if not tg_id:
        return RedirectResponse(f"{redirect_base}?error=telegram_failed", status_code=307)
    name = (str(params.get("first_name") or "") + " " + str(params.get("last_name") or "")).strip() or params.get("username")
    user = await oauth_service.find_or_create_oauth_user(
        session, provider="telegram", sub=str(tg_id), email=None, name=name,
    )
    await track_event("oauth_login", user_id=user.id, props={"provider": "telegram"})
    token = create_jwt(user.id, user.email)
    return RedirectResponse(f"{redirect_base}?token={token}", status_code=307)


@router.post("/telegram")
async def telegram_login(
    body: dict,
    request: Request,
    session: AsyncSession = Depends(get_db),
):
    await enforce_rate_limit(request, scope="oauth_telegram", limit=20, window_seconds=300)
    if not oauth_service.provider_enabled("telegram"):
        raise HTTPException(404, "Telegram-вход не настроен")
    if not oauth_service.verify_telegram_auth(dict(body)):
        raise HTTPException(401, "Подпись Telegram недействительна")
    tg_id = body.get("id")
    if not tg_id:
        raise HTTPException(400, "Некорректные данные Telegram")
    name = (str(body.get("first_name") or "") + " " + str(body.get("last_name") or "")).strip() or body.get("username")
    user = await oauth_service.find_or_create_oauth_user(
        session, provider="telegram", sub=str(tg_id), email=None, name=name,
    )
    await track_event("oauth_login", user_id=user.id, props={"provider": "telegram"})
    token = create_jwt(user.id, user.email)
    return {"token": token, "id": user.id, "email": user.email}

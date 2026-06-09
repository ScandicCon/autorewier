from fastapi import APIRouter, Depends, HTTPException, Request, Response
from sqlalchemy.ext.asyncio import AsyncSession

from app.config import settings
from app.database import get_db
from app.deps import get_current_user
from app.models import User
from app.schemas import LoginRequest, RegisterRequest
from app.services.subscription import is_pro_active
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

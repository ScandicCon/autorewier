import json

from fastapi import APIRouter, Depends, Form, HTTPException, Request
from fastapi.responses import HTMLResponse, RedirectResponse
from fastapi.templating import Jinja2Templates
from sqlalchemy.ext.asyncio import AsyncSession

from app.config import BASE_DIR, settings
from app.database import get_db
from app.deps import get_current_user
from app.models import User
from app.schemas import InspectionCreate, InspectionPostUpdate, VehicleInput
from app.security.rate_limit import enforce_rate_limit
from app.services.auth import (
    COOKIE_NAME,
    authenticate_user,
    register_user,
    session_cookie_kwargs,
)
from app.services.inspections import (
    complete_post_inspection,
    create_inspection,
    get_inspection,
    list_user_inspections,
    run_vin_check,
)
from app.services.listing_text import repairs_to_text
from app.services.parsers import is_avito_url, parse_avito_url
from app.services.subscription import (
    can_create_inspection,
    create_yookassa_payment,
    is_pro_active,
)

router = APIRouter(tags=["cabinet"])
templates = Jinja2Templates(directory=str(BASE_DIR / "web" / "templates"))
_STRUCTURED_MARKER = "--- structured findings ---"


def _ctx(request: Request, user: User | None = None, **extra):
    return {
        "request": request,
        "user": user,
        "is_pro": is_pro_active(user) if user else False,
        "settings": settings,
        **extra,
    }


def _render(
    request: Request,
    name: str,
    user: User | None = None,
    status_code: int = 200,
    **extra,
):
    return templates.TemplateResponse(
        request, name, _ctx(request, user, **extra), status_code=status_code
    )


def _parse_json_list(raw: str) -> list[dict]:
    if not raw or not raw.strip():
        return []
    try:
        data = json.loads(raw)
    except json.JSONDecodeError:
        return []
    if not isinstance(data, list):
        return []
    return [item for item in data if isinstance(item, dict)]


def _split_fallback_text(text: str, has_structured_payload: bool) -> str:
    cleaned = (text or "").strip()
    if not has_structured_payload:
        return cleaned
    return cleaned.split(_STRUCTURED_MARKER)[0].strip()


@router.get("/", response_class=HTMLResponse)
async def landing(request: Request):
    return _render(request, "landing.html")


@router.get("/cabinet/login", response_class=HTMLResponse)
async def login_page(request: Request):
    return _render(request, "login.html", form_email="")


@router.post("/cabinet/login")
async def login_submit(
    request: Request,
    email: str = Form(...),
    password: str = Form(...),
    session: AsyncSession = Depends(get_db),
):
    await enforce_rate_limit(
        request,
        scope="web_login",
        limit=settings.rate_limit_login_limit,
        window_seconds=settings.rate_limit_login_window_seconds,
    )
    user = await authenticate_user(session, email, password)
    if not user:
        return _render(
            request,
            "login.html",
            error="Неверный email или пароль",
            form_email=email,
            status_code=401,
        )
    resp = RedirectResponse("/cabinet", status_code=303)
    resp.set_cookie(COOKIE_NAME, user.session_token, **session_cookie_kwargs())
    return resp


@router.get("/cabinet/register", response_class=HTMLResponse)
async def register_page(request: Request):
    return _render(request, "register.html", form_email="")


@router.post("/cabinet/register")
async def register_submit(
    request: Request,
    email: str = Form(...),
    password: str = Form(...),
    session: AsyncSession = Depends(get_db),
):
    await enforce_rate_limit(
        request,
        scope="web_register",
        limit=settings.rate_limit_register_limit,
        window_seconds=settings.rate_limit_register_window_seconds,
    )
    try:
        user = await register_user(session, email, password)
    except ValueError as e:
        return _render(
            request,
            "register.html",
            error=str(e),
            form_email=email,
            status_code=400,
        )
    resp = RedirectResponse("/cabinet", status_code=303)
    resp.set_cookie(COOKIE_NAME, user.session_token, **session_cookie_kwargs())
    return resp


@router.get("/cabinet", response_class=HTMLResponse)
async def dashboard(
    request: Request,
    user: User = Depends(get_current_user),
    session: AsyncSession = Depends(get_db),
):
    items = await list_user_inspections(session, user.id, limit=30)
    allowed, limit_msg = can_create_inspection(user)
    return _render(
        request,
        "dashboard.html",
        user,
        inspections=items,
        can_create=allowed,
        limit_msg=limit_msg,
    )


@router.get("/cabinet/new", response_class=HTMLResponse)
async def new_inspection_page(request: Request, user: User = Depends(get_current_user)):
    return _render(request, "inspection_new.html", user)


@router.post("/cabinet/new/avito")
async def new_inspection_avito(
    request: Request,
    user: User = Depends(get_current_user),
    listing_url: str = Form(...),
):
    url = listing_url.strip()
    if not is_avito_url(url):
        return _render(
            request,
            "inspection_new.html",
            user,
            error="Нужна ссылка на avito.ru",
            status_code=400,
        )
    parsed = await parse_avito_url(url)
    v = parsed.vehicle
    repairs_text = repairs_to_text(parsed.listing_repairs or [])
    seller_desc = (v.description or "").strip()
    return _render(
        request,
        "inspection_new_form.html",
        user,
        from_avito=True,
        manual=False,
        avito_loaded=parsed.parse_ok,
        parse_warning=None if parsed.parse_ok else parsed.parse_error,
        parse_status=parsed.parse_status,
        parse_reason=parsed.parse_reason,
        action_required=parsed.action_required,
        listing_url=url,
        brand=v.brand or "",
        model=v.model or "",
        year=v.year or "",
        mileage_km=v.mileage_km or "",
        price_rub=v.price_rub or "",
        vin=v.vin or "",
        seller_description=seller_desc,
        listing_repairs=repairs_text,
    )


@router.get("/cabinet/new/manual", response_class=HTMLResponse)
async def new_inspection_manual(request: Request, user: User = Depends(get_current_user)):
    return _render(
        request,
        "inspection_new_form.html",
        user,
        from_avito=False,
        manual=True,
        avito_loaded=False,
        listing_url="",
        brand="",
        model="",
        year="",
        mileage_km="",
        price_rub="",
        vin="",
        seller_description="",
        listing_repairs="",
    )


@router.post("/cabinet/new")
async def new_inspection_submit(
    request: Request,
    user: User = Depends(get_current_user),
    session: AsyncSession = Depends(get_db),
    listing_url: str = Form(""),
    from_avito: str = Form(""),
    avito_loaded: str = Form(""),
    brand: str = Form(""),
    model: str = Form(""),
    year: str = Form(""),
    mileage_km: str = Form(""),
    price_rub: str = Form(""),
    vin: str = Form(""),
    user_preferences: str = Form(""),
    seller_description: str = Form(""),
    listing_repairs: str = Form(""),
    pre_defects: str = Form(""),
    observed_defects_json: str = Form(""),
    photos_metadata_json: str = Form(""),
    is_reseller: str = Form(""),
    target_resale_price: str = Form(""),
):
    def _int(s: str) -> int | None:
        d = "".join(c for c in s if c.isdigit())
        return int(d) if d else None

    url = listing_url.strip() or None
    vehicle = VehicleInput(
        brand=brand or None,
        model=model or None,
        year=_int(year),
        mileage_km=_int(mileage_km),
        price_rub=_int(price_rub),
        vin=vin.strip().upper() or None,
        description=seller_description.strip() or None,
    )
    observed_defects = _parse_json_list(observed_defects_json)
    photos_metadata = _parse_json_list(photos_metadata_json)
    has_structured_payload = bool(observed_defects or photos_metadata)

    body = InspectionCreate(
        listing_url=url,
        vehicle=vehicle,
        user_preferences=user_preferences or None,
        listing_repairs=listing_repairs or None,
        pre_defects=_split_fallback_text(pre_defects, has_structured_payload) or None,
        observed_defects=observed_defects,
        photos_metadata=photos_metadata,
        is_reseller=is_reseller == "on",
        target_resale_price=_int(target_resale_price),
        require_avito_parse=bool(from_avito and avito_loaded and url),
    )
    try:
        ins = await create_inspection(session, user, body)
    except PermissionError as e:
        return _render(
            request,
            "inspection_new_form.html",
            user,
            error=str(e),
            manual=not from_avito,
            status_code=402,
        )
    except ValueError as e:
        return _render(
            request,
            "inspection_new_form.html",
            user,
            error=str(e),
            from_avito=bool(from_avito),
            manual=not from_avito,
            listing_url=url or "",
            brand=brand,
            model=model,
            status_code=400,
        )
    return RedirectResponse(f"/cabinet/inspection/{ins.id}", status_code=303)


@router.get("/cabinet/inspection/{inspection_id}", response_class=HTMLResponse)
async def inspection_detail(
    inspection_id: int,
    request: Request,
    user: User = Depends(get_current_user),
    session: AsyncSession = Depends(get_db),
):
    ins = await get_inspection(session, inspection_id, user.id)
    if not ins:
        raise HTTPException(404)
    report = ins.post_report or ins.pre_report or {}
    parts = ins.parts_pricing or report.get("parts_pricing") or []
    return _render(
        request,
        "inspection_detail.html",
        user,
        inspection=ins,
        report=report,
        parts_pricing=parts,
        report_json=json.dumps(report, ensure_ascii=False, default=str),
    )


@router.post("/cabinet/inspection/{inspection_id}/post")
async def inspection_post_submit(
    inspection_id: int,
    request: Request,
    user: User = Depends(get_current_user),
    session: AsyncSession = Depends(get_db),
    post_defects: str = Form(...),
    post_notes: str = Form(""),
    observed_defects_json: str = Form(""),
    photos_metadata_json: str = Form(""),
):
    observed_defects = _parse_json_list(observed_defects_json)
    photos_metadata = _parse_json_list(photos_metadata_json)
    has_structured_payload = bool(observed_defects or photos_metadata)

    ins = await complete_post_inspection(
        session,
        inspection_id,
        user.id,
        InspectionPostUpdate(
            post_defects=_split_fallback_text(post_defects, has_structured_payload),
            post_notes=post_notes or None,
            observed_defects=observed_defects,
            photos_metadata=photos_metadata,
        ),
    )
    if not ins:
        raise HTTPException(404)
    return RedirectResponse(f"/cabinet/inspection/{ins.id}", status_code=303)


@router.post("/cabinet/inspection/{inspection_id}/vin")
async def inspection_vin_submit(
    inspection_id: int,
    request: Request,
    user: User = Depends(get_current_user),
    session: AsyncSession = Depends(get_db),
    vin: str = Form(...),
):
    try:
        await run_vin_check(session, user.id, vin.strip(), inspection_id)
    except Exception as e:
        ins = await get_inspection(session, inspection_id, user.id)
        report = ins.post_report or ins.pre_report or {} if ins else {}
        parts = (ins.parts_pricing if ins else None) or report.get("parts_pricing") or []
        return _render(
            request,
            "inspection_detail.html",
            user,
            inspection=ins,
            report=report,
            parts_pricing=parts,
            vin_error=str(e),
            status_code=502,
        )
    return RedirectResponse(f"/cabinet/inspection/{inspection_id}", status_code=303)


@router.get("/cabinet/subscription", response_class=HTMLResponse)
async def subscription_page(
    request: Request,
    user: User = Depends(get_current_user),
    paid: str = "",
):
    return _render(request, "subscription.html", user, paid=paid == "1")


@router.post("/cabinet/subscription/pay")
async def subscription_pay(
    request: Request,
    user: User = Depends(get_current_user),
    session: AsyncSession = Depends(get_db),
):
    await enforce_rate_limit(
        request,
        scope="web_payment",
        limit=settings.rate_limit_payment_limit,
        window_seconds=settings.rate_limit_payment_window_seconds,
        identity=str(user.id),
    )
    if not settings.yookassa_enabled:
        if not settings.can_use_dev_payment_bypass:
            raise HTTPException(503, "Payment provider is not configured")
        from app.services.subscription import activate_pro_subscription

        await activate_pro_subscription(session, user)
        return RedirectResponse("/cabinet/subscription?paid=1", status_code=303)
    data = await create_yookassa_payment(session, user)
    return RedirectResponse(data["confirmation_url"], status_code=303)

from fastapi import APIRouter, Depends, HTTPException, Request
from fastapi.responses import Response
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.config import settings
from app.database import get_db
from app.deps import get_current_user, get_user_id
from app.models import User
from app.security.rate_limit import enforce_rate_limit
from app.schemas import (
    AnalysisReport,
    AvitoWarmupRequest,
    AvitoWarmupResponse,
    CompareRequest,
    CompareResult,
    CompareItem,
    InspectionComparisonResponse,
    InspectionCreate,
    InspectionPostUpdate,
    InspectionResponse,
    ListingChangeEventResponse,
    MonitoredListingCreate,
    MonitoredListingResponse,
    ParseListingRequest,
    ParseListingResponse,
    TaskStatusResponse,
    VinCheckRequest,
    VinCheckResponse,
    VinCheckTaskCreateResponse,
)
from app.services.inspections import (
    build_comparison_items,
    complete_post_inspection,
    create_inspection,
    get_inspection,
    list_user_inspections,
    run_vin_check,
)
from app.services.analytics import track_event
from app.services.parsers import parse_listing_url
from app.services.parsers.avito_fetch import AvitoFetchStatus, warmup_avito_session
from app.services.subscription import is_pro_active
from app.services.task_queue import enqueue_tracked_task, get_task_status

router = APIRouter()


@router.get("/health")
async def health():
    return {"status": "ok", "service": "autorewier"}


@router.get("/me")
async def me(user: User = Depends(get_current_user)):
    return {
        "id": user.id,
        "email": user.email,
        "telegram_id": user.telegram_id,
        "email_verified": bool(user.email_verified),
        "phone_number": user.phone_number,
        "phone_verified": bool(user.phone_verified),
        "plan": user.subscription_plan.value,
        "pro_until": user.subscription_until.isoformat() if user.subscription_until else None,
        "is_pro": is_pro_active(user),
        "inspections_this_month": user.inspections_this_month,
    }


@router.post("/parse-listing", response_model=ParseListingResponse)
async def parse_listing(
    body: ParseListingRequest,
    request: Request,
    user: User = Depends(get_current_user),
):
    await enforce_rate_limit(
        request,
        scope="parse_listing",
        limit=settings.rate_limit_vin_limit,
        window_seconds=settings.rate_limit_vin_window_seconds,
        identity=str(user.id),
    )
    parsed = await parse_listing_url(str(body.url))
    return ParseListingResponse(
        platform=parsed.platform,
        vehicle=parsed.vehicle,
        raw_title=parsed.raw_title,
        parse_ok=parsed.parse_ok,
        parse_error=parsed.parse_error,
        parse_status=parsed.parse_status,
        parse_reason=parsed.parse_reason,
        action_required=parsed.action_required,
        listing_repairs=parsed.listing_repairs or [],
        photo_urls=parsed.photo_urls or [],
    )


@router.post("/avito/warmup", response_model=AvitoWarmupResponse)
async def avito_warmup(body: AvitoWarmupRequest, user: User = Depends(get_current_user)):
    result = await warmup_avito_session(str(body.url) if body.url else None)
    reason = result.reason or ("warmup_ready" if result.status == AvitoFetchStatus.success else "fetch_failed")
    return AvitoWarmupResponse(
        status=result.status.value,
        reason=reason,
        action_required=result.action_required,
        message=result.user_message,
        attempts=result.attempts,
        diagnostics=result.diagnostics,
    )


@router.post("/inspections", response_model=InspectionResponse)
async def create_inspection_api(
    body: InspectionCreate,
    request: Request,
    user: User = Depends(get_current_user),
    session: AsyncSession = Depends(get_db),
):
    if (settings.enforce_verified_accounts or settings.require_email_verification) and not (
        bool(user.email_verified) or bool(user.phone_verified)
    ):
        raise HTTPException(
            403,
            "Confirm account (email or phone) to create inspections.",
        )
    await enforce_rate_limit(
        request,
        scope="create_inspection",
        limit=settings.rate_limit_vin_limit,
        window_seconds=settings.rate_limit_vin_window_seconds,
        identity=str(user.id),
    )
    try:
        ins = await create_inspection(session, user, body)
    except PermissionError as e:
        raise HTTPException(402, str(e)) from e
    except ValueError as e:
        raise HTTPException(400, str(e)) from e
    await track_event("inspection_created", user_id=user.id, props={"origin": "api"})
    return _to_response(ins)


@router.get("/inspections", response_model=list[InspectionResponse])
async def list_inspections(
    user_id: int = Depends(get_user_id),
    session: AsyncSession = Depends(get_db),
):
    items = await list_user_inspections(session, user_id)
    return [_to_response(i) for i in items]


@router.get("/inspections/{inspection_id}", response_model=InspectionResponse)
async def get_inspection_api(
    inspection_id: int,
    user_id: int = Depends(get_user_id),
    session: AsyncSession = Depends(get_db),
):
    ins = await get_inspection(session, inspection_id, user_id)
    if not ins:
        raise HTTPException(404, "Inspection not found")
    return _to_response(ins)


@router.post("/inspections/{inspection_id}/post", response_model=InspectionResponse)
async def post_inspection_api(
    inspection_id: int,
    body: InspectionPostUpdate,
    user_id: int = Depends(get_user_id),
    session: AsyncSession = Depends(get_db),
):
    ins = await complete_post_inspection(session, inspection_id, user_id, body)
    if not ins:
        raise HTTPException(404, "Inspection not found")
    return _to_response(ins)


@router.post("/inspections/{inspection_id}/findings", response_model=InspectionResponse)
async def save_findings_api(
    inspection_id: int,
    body: InspectionPostUpdate,
    user_id: int = Depends(get_user_id),
    session: AsyncSession = Depends(get_db),
):
    ins = await complete_post_inspection(session, inspection_id, user_id, body)
    if not ins:
        raise HTTPException(404, "Inspection not found")
    return _to_response(ins)


@router.get("/inspections-comparison", response_model=InspectionComparisonResponse)
async def compare_inspections_api(
    ids: list[int],
    user_id: int = Depends(get_user_id),
    session: AsyncSession = Depends(get_db),
):
    selected: list = []
    for inspection_id in ids[:10]:
        ins = await get_inspection(session, inspection_id, user_id)
        if ins:
            selected.append(ins)
    return InspectionComparisonResponse(items=build_comparison_items(selected))


@router.get("/inspections/{inspection_id}/checklist")
async def get_checklist(
    inspection_id: int,
    user_id: int = Depends(get_user_id),
    session: AsyncSession = Depends(get_db),
):
    ins = await get_inspection(session, inspection_id, user_id)
    if not ins:
        raise HTTPException(404, "Inspection not found")
    report_data = ins.post_report or ins.pre_report
    if not report_data:
        raise HTTPException(404, "Report not found")
    report = AnalysisReport(**report_data)
    return {"checklist": [c.model_dump() for c in report.checklist]}


@router.post("/vin/check", response_model=VinCheckResponse)
async def vin_check_api(
    body: VinCheckRequest,
    request: Request,
    user: User = Depends(get_current_user),
    session: AsyncSession = Depends(get_db),
):
    await enforce_rate_limit(
        request,
        scope="vin_check",
        limit=settings.rate_limit_vin_limit,
        window_seconds=settings.rate_limit_vin_window_seconds,
        identity=str(user.id),
    )
    try:
        check = await run_vin_check(session, user.id, body.vin, body.inspection_id)
    except ValueError as e:
        raise HTTPException(402, str(e)) from e
    except Exception as e:
        raise HTTPException(502, f"Autocode: {e}") from e
    return VinCheckResponse(
        id=check.id,
        vin=check.vin,
        summary=check.summary,
        report_uid=check.report_uid,
        created_at=check.created_at,
    )


@router.post("/vin/check/async", response_model=VinCheckTaskCreateResponse, status_code=202)
async def vin_check_async_api(
    body: VinCheckRequest,
    request: Request,
    user: User = Depends(get_current_user),
):
    await enforce_rate_limit(
        request,
        scope="vin_check_async",
        limit=settings.rate_limit_vin_limit,
        window_seconds=settings.rate_limit_vin_window_seconds,
        identity=str(user.id),
    )
    task_id = await enqueue_tracked_task(
        "vin_check",
        {"user_id": user.id, "vin": body.vin, "inspection_id": body.inspection_id},
        owner_id=user.id,
    )
    if not task_id:
        raise HTTPException(503, "Task queue is unavailable")
    status = await get_task_status(task_id)
    if not status:
        raise HTTPException(503, "Task queue accepted task but status is unavailable")
    return VinCheckTaskCreateResponse(
        task_id=task_id,
        task=status.get("task", "vin_check"),
        status=status.get("status", "queued"),
        created_at=status.get("created_at"),
    )


@router.get("/tasks/{task_id}", response_model=TaskStatusResponse)
async def get_task_status_api(
    task_id: str,
    user: User = Depends(get_current_user),
):
    status = await get_task_status(task_id)
    if not status:
        raise HTTPException(404, "Task not found")
    owner_id = status.get("owner_id")
    if owner_id is not None and owner_id != user.id:
        raise HTTPException(404, "Task not found")
    return TaskStatusResponse(
        task_id=status["task_id"],
        task=status["task"],
        status=status["status"],
        created_at=status.get("created_at"),
        updated_at=status.get("updated_at"),
        result=status.get("result"),
        error=status.get("error"),
    )


@router.get("/inspections/{inspection_id}/pdf")
async def download_inspection_pdf(
    inspection_id: int,
    user_id: int = Depends(get_user_id),
    session: AsyncSession = Depends(get_db),
) -> Response:
    ins = await get_inspection(session, inspection_id, user_id)
    if not ins:
        raise HTTPException(404, "Inspection not found")
    report_data = ins.post_report or ins.pre_report
    if not report_data:
        raise HTTPException(404, "Report not generated yet")
    try:
        report = AnalysisReport(**report_data)
    except Exception as exc:
        raise HTTPException(422, f"Report parse error: {exc}") from exc
    parts = [ins.brand, ins.model, str(ins.year) if ins.year else None]
    vehicle_label = " ".join(p for p in parts if p) or f"Inspection #{inspection_id}"
    try:
        from app.services.pdf_report import generate_inspection_pdf
        pdf_bytes = generate_inspection_pdf(report, vehicle_label)
    except Exception as exc:
        raise HTTPException(500, f"PDF generation error: {exc}") from exc
    return Response(
        content=pdf_bytes,
        media_type="application/pdf",
        headers={"Content-Disposition": f"attachment; filename=inspection_{inspection_id}.pdf"},
    )


# ---------------------------------------------------------------------------
# Monitored listings
# ---------------------------------------------------------------------------

@router.post("/monitored-listings", response_model=MonitoredListingResponse, status_code=201)
async def add_monitored_listing(
    body: MonitoredListingCreate,
    user: User = Depends(get_current_user),
    session: AsyncSession = Depends(get_db),
):
    from app.models import MonitoredListing
    from app.services.parsers.base import _detect_platform

    platform = _detect_platform(body.url)
    listing = MonitoredListing(
        user_id=user.id,
        inspection_id=body.inspection_id,
        url=body.url,
        platform=platform,
    )
    session.add(listing)
    await session.commit()
    await session.refresh(listing)
    return listing


@router.get("/monitored-listings", response_model=list[MonitoredListingResponse])
async def list_monitored_listings(
    user: User = Depends(get_current_user),
    session: AsyncSession = Depends(get_db),
):
    from app.models import MonitoredListing

    result = await session.execute(
        select(MonitoredListing)
        .where(MonitoredListing.user_id == user.id)
        .order_by(MonitoredListing.created_at.desc())
    )
    return list(result.scalars().all())


@router.delete("/monitored-listings/{listing_id}", status_code=204)
async def delete_monitored_listing(
    listing_id: int,
    user: User = Depends(get_current_user),
    session: AsyncSession = Depends(get_db),
):
    from app.models import MonitoredListing

    listing = await session.get(MonitoredListing, listing_id)
    if not listing or listing.user_id != user.id:
        raise HTTPException(404, "Not found")
    await session.delete(listing)
    await session.commit()


@router.get(
    "/monitored-listings/{listing_id}/events",
    response_model=list[ListingChangeEventResponse],
)
async def get_listing_events(
    listing_id: int,
    user: User = Depends(get_current_user),
    session: AsyncSession = Depends(get_db),
):
    from app.models import ListingChangeEvent, MonitoredListing

    listing = await session.get(MonitoredListing, listing_id)
    if not listing or listing.user_id != user.id:
        raise HTTPException(404, "Not found")
    result = await session.execute(
        select(ListingChangeEvent)
        .where(ListingChangeEvent.monitored_listing_id == listing_id)
        .order_by(ListingChangeEvent.created_at.desc())
    )
    return list(result.scalars().all())


# ---------------------------------------------------------------------------
# Compare inspections (POST body version)
# ---------------------------------------------------------------------------

@router.post("/inspections/compare", response_model=CompareResult)
async def compare_inspections_post(
    body: CompareRequest,
    user_id: int = Depends(get_user_id),
    session: AsyncSession = Depends(get_db),
):
    selected = []
    for iid in body.inspection_ids[:3]:
        ins = await get_inspection(session, iid, user_id)
        if ins:
            selected.append(ins)

    if len(selected) < 2:
        raise HTTPException(400, "Need at least 2 accessible inspections to compare")

    items: list[CompareItem] = []
    for ins in selected:
        label = f"{ins.brand or ''} {ins.model or ''} {ins.year or ''}".strip() or f"#{ins.id}"
        repair_min = ins.repair_min_rub or 0
        repair_max = ins.repair_max_rub or 0
        repair_mid = (repair_min + repair_max) // 2 if (repair_min or repair_max) else None
        risk_score: int | None = None
        report_data = ins.post_report or ins.pre_report
        if report_data and isinstance(report_data, dict):
            risk_score = report_data.get("risk_score")
        items.append(CompareItem(
            inspection_id=ins.id,
            label=label,
            brand=ins.brand,
            model=ins.model,
            year=ins.year,
            price_rub=ins.price_rub,
            repair_min_rub=ins.repair_min_rub,
            repair_max_rub=ins.repair_max_rub,
            repair_mid_rub=repair_mid,
            risk_score=risk_score,
            verdict=ins.verdict.value if ins.verdict else None,
            final_recommendation=ins.final_recommendation,
        ))

    winner_id: int | None = None
    winner_reason: str | None = None
    scored = []
    for item in items:
        price = item.price_rub or 0
        repair = item.repair_mid_rub or 0
        risk = item.risk_score or 50
        score = price + repair + risk * 1000
        scored.append((score, item.inspection_id, item))
    if scored:
        scored.sort(key=lambda x: x[0])
        _, best_id, best_item = scored[0]
        winner_id = best_id
        parts = []
        if best_item.price_rub:
            parts.append(f"price {best_item.price_rub:,} RUB")
        if best_item.repair_mid_rub:
            parts.append(f"repair ~{best_item.repair_mid_rub:,} RUB")
        if best_item.risk_score is not None:
            parts.append(f"risk score {best_item.risk_score}")
        winner_reason = "Best ratio: " + ", ".join(parts) if parts else "Lowest combined cost"

    return CompareResult(items=items, winner_id=winner_id, winner_reason=winner_reason)


def _to_response(ins) -> InspectionResponse:
    return InspectionResponse(
        id=ins.id,
        stage=ins.stage.value,
        listing_url=ins.listing_url,
        brand=ins.brand,
        model=ins.model,
        year=ins.year,
        mileage_km=ins.mileage_km,
        price_rub=ins.price_rub,
        vin=ins.vin,
        verdict=ins.verdict.value if ins.verdict else None,
        final_recommendation=ins.final_recommendation,
        pre_report=ins.pre_report,
        post_report=ins.post_report,
        parts_pricing=ins.parts_pricing,
        observed_defects=ins.observed_defects or [],
        photos_metadata=ins.photos_metadata or [],
        repair_min_rub=ins.repair_min_rub,
        repair_max_rub=ins.repair_max_rub,
        post_notes=ins.post_notes,
        created_at=ins.created_at,
    )

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from pydantic import ValidationError

from app.models import Inspection, InspectionStage, User, Verdict, VinCheck
from app.schemas import (
    AnalysisReport,
    ImageFinding,
    InspectionComparisonItem,
    InspectionCreate,
    InspectionPostUpdate,
    ObservedDefectInput,
    PhotoMetadataInput,
    VehicleInput,
)
from app.services.analysis import (
    build_analysis_report,
    build_replacement_suggestions,
    maybe_enrich_with_llm,
)
from app.services.autocode import request_vin_report
from app.services.image_analysis import analyze_photo_urls
from app.services.listing_text import extract_listing_repairs, repairs_to_text
from app.services.parts_prices import build_parts_pricing
from app.services.parsers import is_avito_url, parse_avito_url, parse_listing_url
from app.services.subscription import (
    can_create_inspection,
    can_use_vin_report,
    consume_vin_report,
    increment_inspection_usage,
)


async def get_or_create_user(session: AsyncSession, telegram_id: int) -> User:
    result = await session.execute(select(User).where(User.telegram_id == telegram_id))
    user = result.scalar_one_or_none()
    if user:
        return user
    user = User(telegram_id=telegram_id)
    session.add(user)
    await session.commit()
    await session.refresh(user)
    return user


def _vehicle_from_inspection(ins: Inspection) -> VehicleInput:
    return VehicleInput(
        brand=ins.brand,
        model=ins.model,
        year=ins.year,
        mileage_km=ins.mileage_km,
        price_rub=ins.price_rub,
        engine=ins.engine,
        transmission=ins.transmission,
        drive=ins.drive,
        body_type=ins.body_type,
        color=ins.color,
        vin=ins.vin,
        description=ins.description,
    )


def _apply_vehicle(ins: Inspection, v: VehicleInput) -> None:
    for field in VehicleInput.model_fields:
        setattr(ins, field, getattr(v, field))


def _parse_repairs_list(text: str | None, vehicle: VehicleInput) -> list[str]:
    if text and text.strip():
        return [ln.strip().lstrip("• ").strip() for ln in text.splitlines() if ln.strip()]
    return extract_listing_repairs(vehicle.description)


def _defects_from_observed(defects: list[ObservedDefectInput]) -> str:
    if not defects:
        return ""
    lines: list[str] = []
    for item in defects:
        bits = [item.title]
        if item.details:
            bits.append(item.details)
        if item.estimated_cost_max:
            bits.append(f"до {item.estimated_cost_max} ₽")
        lines.append(", ".join(bits))
    return "\n".join(lines)


def _dedupe_observed_defects(
    defects: list[ObservedDefectInput],
) -> list[ObservedDefectInput]:
    seen: set[tuple[str, str]] = set()
    out: list[ObservedDefectInput] = []
    for item in defects:
        key = (item.zone.lower().strip(), item.title.lower().strip())
        if key in seen:
            continue
        seen.add(key)
        out.append(item)
    return out


def _normalize_photo_metadata(
    photos: list[PhotoMetadataInput],
) -> list[PhotoMetadataInput]:
    out: list[PhotoMetadataInput] = []
    for p in photos:
        if not p.photo_url and not p.photo_path:
            continue
        out.append(p)
    return out


def _image_findings_to_text(image_findings: list) -> str:
    if not image_findings:
        return ""
    return "\n".join(f"{item.issue}. Зона: {item.zone or 'не указана'}" for item in image_findings)


def _apply_parts_to_report(report: AnalysisReport, parts_blocks) -> AnalysisReport:
    report.parts_pricing = parts_blocks
    report.replacement_suggestions = build_replacement_suggestions(
        report.repair_lines, parts_blocks
    )
    estimates = [b.estimate_min for b in parts_blocks if b.estimate_min is not None]
    estimates_max = [b.estimate_max for b in parts_blocks if b.estimate_max is not None]
    if estimates and estimates_max:
        parts_min = sum(estimates)
        parts_max = sum(estimates_max)
        report.repair_total_min = max(report.repair_total_min, parts_min)
        report.repair_total_max = max(report.repair_total_max, parts_max)
        for line in report.repair_lines:
            related = [b for b in parts_blocks if b.category == line.category]
            if related:
                b = related[0]
                line.parts_hint = (
                    f"Запчасти: ~{b.estimate_min or b.avito_min or line.min_rub:,}–"
                    f"{b.estimate_max or b.avito_max or line.max_rub:,} ₽".replace(",", " ")
                )
    return report


async def _enrich_report(
    report: AnalysisReport,
    vehicle: VehicleInput,
    defects: str | None,
    user_preferences: str | None,
    listing_repairs: list[str],
) -> AnalysisReport:
    report = await maybe_enrich_with_llm(
        report, vehicle, defects, user_preferences, listing_repairs
    )
    categories = [line.category for line in report.repair_lines] or ["Прочее"]
    parts = await build_parts_pricing(vehicle, defects, categories)
    return _apply_parts_to_report(report, parts)


async def create_inspection(
    session: AsyncSession,
    user: User,
    data: InspectionCreate,
) -> Inspection:
    allowed, msg = can_create_inspection(user)
    if not allowed:
        raise PermissionError(msg)

    vehicle = data.vehicle or VehicleInput()
    platform = None
    listing_repairs_list: list[str] = _parse_repairs_list(data.listing_repairs, vehicle)

    if data.listing_url:
        url = data.listing_url.strip()
        if data.require_avito_parse and not is_avito_url(url):
            raise ValueError("Укажите ссылку на объявление Avito (avito.ru) или введите данные вручную")

        # Парсинг объявления:
        #  - Avito тяжёлый (Playwright/скрейпинг) — парсим только по явному
        #    запросу (require_avito_parse), чтобы не упираться в таймаут.
        #  - Остальные площадки (Drom/Auto.ru/Youla/прочие) — лёгкий HTTP-парс,
        #    выполняем всегда, когда дана ссылка.
        parsed = None
        if is_avito_url(url):
            if data.require_avito_parse:
                parsed = await parse_avito_url(url)
        else:
            parsed = await parse_listing_url(url)

        if parsed is not None:
            platform = parsed.platform
            if not parsed.parse_ok:
                raise ValueError(parsed.parse_error or "Не удалось загрузить объявление")

            if not isinstance(parsed.vehicle, VehicleInput):
                raise ValueError("Некорректные данные автомобиля в объявлении")
            merged = parsed.vehicle.model_dump()
            if data.vehicle:
                merged.update(
                    {k: v for k, v in data.vehicle.model_dump().items() if v is not None}
                )
            try:
                vehicle = VehicleInput(**merged)
            except ValidationError as exc:
                raise ValueError("Некорректные данные автомобиля в объявлении") from exc
            if parsed.listing_repairs:
                listing_repairs_list = parsed.listing_repairs

    if not listing_repairs_list:
        listing_repairs_list = extract_listing_repairs(vehicle.description)

    observed_defects = _dedupe_observed_defects(data.observed_defects)
    photos_metadata = _normalize_photo_metadata(data.photos_metadata)
    image_findings = await analyze_photo_urls(photos_metadata)
    if data.extra_image_findings:
        # Ручной анализ фото пользователя (не из объявления) — добавляем к авто-находкам.
        image_findings = [*image_findings, *data.extra_image_findings]
    observed_defects_text = _defects_from_observed(observed_defects)
    image_defects_text = _image_findings_to_text(image_findings)
    pre_defects_text = "\n".join(
        filter(None, [data.pre_defects or "", observed_defects_text, image_defects_text])
    ).strip()

    report = build_analysis_report(
        vehicle,
        defects=pre_defects_text or None,
        user_preferences=data.user_preferences,
        listing_repairs=listing_repairs_list,
        is_reseller=data.is_reseller,
        target_resale_price=data.target_resale_price,
    )
    report = await _enrich_report(
        report,
        vehicle,
        pre_defects_text or None,
        data.user_preferences,
        listing_repairs_list,
    )
    report.image_findings = image_findings
    report.vehicle_passport.source_platform = platform
    report.vehicle_passport.source_listing_url = data.listing_url
    if report.image_findings:
        report.analysis_rationale.append(
            "В отчет добавлены предварительные сигналы по фото-URL. Подтвердите их на очном осмотре."
        )
    if report.parts_pricing and not report.replacement_suggestions:
        report.replacement_suggestions = build_replacement_suggestions(
            report.repair_lines, report.parts_pricing
        )

    vin_summary = None
    vin_raw = None
    vin_uid = None
    if vehicle.vin:
        allowed_vin, vin_msg = can_use_vin_report(user)
        if not allowed_vin:
            report.vin_summary = vin_msg
        else:
            try:
                vin_data = await request_vin_report(vehicle.vin)
                vin_summary = vin_data.get("summary")
                vin_raw = vin_data.get("raw")
                vin_uid = vin_data.get("report_uid")
                report.vin_summary = vin_summary
                consume_vin_report(user)
            except Exception:
                report.vin_summary = "Проверка VIN временно недоступна"

    parts_dump = [p.model_dump() for p in report.parts_pricing]

    ins = Inspection(
        user_id=user.id,
        stage=InspectionStage.PRE_INSPECTION,
        listing_url=data.listing_url,
        platform=platform,
        user_preferences=data.user_preferences,
        listing_repairs=repairs_to_text(listing_repairs_list) or None,
        pre_defects=pre_defects_text or None,
        observed_defects=[d.model_dump() for d in observed_defects],
        photos_metadata=[p.model_dump() for p in photos_metadata],
        is_reseller=data.is_reseller,
        target_resale_price=data.target_resale_price,
        final_recommendation=report.final_recommendation.value,
        verdict=Verdict(report.verdict.value),
        pre_report=report.model_dump(),
        parts_pricing=parts_dump,
        repair_min_rub=report.repair_total_min,
        repair_max_rub=report.repair_total_max,
    )
    _apply_vehicle(ins, vehicle)
    session.add(ins)
    increment_inspection_usage(user)
    await session.commit()
    await session.refresh(ins)

    if vehicle.vin and vin_summary:
        session.add(
            VinCheck(
                user_id=user.id,
                inspection_id=ins.id,
                vin=vehicle.vin.upper(),
                report_uid=vin_uid,
                summary=vin_summary,
                report_data=vin_raw,
            )
        )
        await session.commit()

    return ins


async def run_vin_check(
    session: AsyncSession,
    user_id: int,
    vin: str,
    inspection_id: int | None = None,
) -> VinCheck:
    user = await session.get(User, user_id)
    if user is not None:
        allowed_vin, vin_msg = can_use_vin_report(user)
        if not allowed_vin:
            raise ValueError(vin_msg)
    data = await request_vin_report(vin)
    check = VinCheck(
        user_id=user_id,
        inspection_id=inspection_id,
        vin=vin.upper(),
        report_uid=data.get("report_uid"),
        summary=data.get("summary"),
        report_data=data.get("raw"),
    )
    session.add(check)
    if inspection_id:
        ins = await session.get(Inspection, inspection_id)
        if ins and ins.user_id == user_id:
            ins.vin = vin.upper()
            if ins.pre_report:
                pr = dict(ins.pre_report)
                pr["vin_summary"] = data.get("summary")
                ins.pre_report = pr
    if user is not None:
        consume_vin_report(user)
    await session.commit()
    await session.refresh(check)
    return check


async def complete_post_inspection(
    session: AsyncSession,
    inspection_id: int,
    user_id: int,
    data: InspectionPostUpdate,
) -> Inspection | None:
    result = await session.execute(
        select(Inspection).where(
            Inspection.id == inspection_id,
            Inspection.user_id == user_id,
        )
    )
    ins = result.scalar_one_or_none()
    if not ins:
        return None

    vehicle = _vehicle_from_inspection(ins)
    repairs = _parse_repairs_list(ins.listing_repairs, vehicle)
    observed_defects = _dedupe_observed_defects(data.observed_defects)
    photos_metadata = _normalize_photo_metadata(data.photos_metadata)
    image_findings = await analyze_photo_urls(photos_metadata)
    observed_defects_text = _defects_from_observed(observed_defects)
    image_defects_text = _image_findings_to_text(image_findings)
    combined_defects = "\n".join(
        filter(None, [ins.pre_defects, data.post_defects, observed_defects_text, image_defects_text])
    )
    report = build_analysis_report(
        vehicle,
        defects=combined_defects,
        user_preferences=ins.user_preferences,
        listing_repairs=repairs,
        is_reseller=ins.is_reseller,
        target_resale_price=ins.target_resale_price,
        post_inspection=True,
    )
    report = await _enrich_report(
        report,
        vehicle,
        combined_defects,
        ins.user_preferences,
        repairs,
    )
    report.image_findings = image_findings
    report.vehicle_passport.source_platform = ins.platform
    report.vehicle_passport.source_listing_url = ins.listing_url
    if report.image_findings:
        report.analysis_rationale.append(
            "В отчет добавлены предварительные сигналы по фото-URL. Подтвердите их на очном осмотре."
        )
    if report.parts_pricing and not report.replacement_suggestions:
        report.replacement_suggestions = build_replacement_suggestions(
            report.repair_lines, report.parts_pricing
        )
    if ins.pre_report and ins.pre_report.get("vin_summary"):
        report.vin_summary = ins.pre_report["vin_summary"]

    ins.post_defects = data.post_defects
    ins.post_notes = data.post_notes
    if observed_defects:
        ins.observed_defects = [d.model_dump() for d in observed_defects]
    if photos_metadata:
        ins.photos_metadata = [p.model_dump() for p in photos_metadata]
    ins.stage = InspectionStage.POST_INSPECTION
    ins.final_recommendation = report.final_recommendation.value
    ins.verdict = Verdict(report.verdict.value)
    ins.post_report = report.model_dump()
    ins.parts_pricing = [p.model_dump() for p in report.parts_pricing]
    ins.repair_min_rub = report.repair_total_min
    ins.repair_max_rub = report.repair_total_max
    await session.commit()
    await session.refresh(ins)
    return ins


async def list_user_inspections(
    session: AsyncSession, user_id: int, limit: int = 20
) -> list[Inspection]:
    result = await session.execute(
        select(Inspection)
        .where(Inspection.user_id == user_id)
        .order_by(Inspection.created_at.desc())
        .limit(limit)
    )
    return list(result.scalars().all())


async def get_inspection(
    session: AsyncSession, inspection_id: int, user_id: int
) -> Inspection | None:
    result = await session.execute(
        select(Inspection).where(
            Inspection.id == inspection_id,
            Inspection.user_id == user_id,
        )
    )
    return result.scalar_one_or_none()


def build_comparison_items(inspections: list[Inspection]) -> list[InspectionComparisonItem]:
    items: list[InspectionComparisonItem] = []
    for ins in inspections:
        source = ins.post_report or ins.pre_report or {}
        resale = source.get("resale") if isinstance(source, dict) else None
        repair_mid = None
        if ins.repair_min_rub is not None and ins.repair_max_rub is not None:
            repair_mid = (ins.repair_min_rub + ins.repair_max_rub) // 2
        projected_total = (
            (ins.price_rub or 0) + (repair_mid or 0) if ins.price_rub is not None else None
        )
        label_bits = [x for x in [ins.brand, ins.model] if x]
        if ins.year:
            label_bits.append(str(ins.year))
        items.append(
            InspectionComparisonItem(
                inspection_id=ins.id,
                label=" ".join(label_bits) or f"Inspection #{ins.id}",
                price_rub=ins.price_rub,
                repair_mid_rub=repair_mid,
                projected_total_rub=projected_total,
                final_recommendation=ins.final_recommendation,
                verdict=ins.verdict.value if ins.verdict else None,
                estimated_margin=(resale or {}).get("estimated_margin")
                if isinstance(resale, dict)
                else None,
            )
        )
    return items

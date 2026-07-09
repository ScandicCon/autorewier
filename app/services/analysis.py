import json
from pathlib import Path
from urllib.parse import urlparse

from app.config import settings
from app.schemas import (
    AnalysisReport,
    EvidenceItem,
    FinalRecommendationEnum,
    PartPriceBlock,
    RepairLine,
    ReplacementPartSuggestion,
    ResaleEconomics,
    RiskSeverityEnum,
    RiskItem,
    VehiclePassport,
    VehicleInput,
    VerdictEnum,
)
from app.services.checklist import build_checklist
from app.services.listing_text import (
    analyze_user_preferences,
    extract_listing_repairs,
    repair_categories_claimed,
    repairs_to_text,
)
from app.services.parts_prices import build_avito_search_url

DATA_DIR = Path(__file__).resolve().parent.parent / "data"

VERDICT_LABELS = {
    VerdictEnum.worth_looking: "Стоит смотреть",
    VerdictEnum.caution: "Стоит смотреть с осторожностью",
    VerdictEnum.skip: "Не стоит рассматривать",
}

# ~17 тыс. км/год — ориентир для РФ; не штрафуем умеренный пробег
KM_PER_YEAR_NORM = 17_000
MILEAGE_RATIO_CAUTION = 1.45
MILEAGE_RATIO_HIGH = 1.85

# Риски-справка: не должны сами переводить в «не стоит»
INFO_RISK_TITLES = frozenset(
    {
        "Пробег",
        "Пробег для года",
        "Возраст автомобиля",
        "Типичная слабость модели",
        "Заявлено в объявлении",
        "Обслуживание по объявлению",
        "Ваши пожелания",
    }
)

# Слова о ТО/заменах в описании не считаем «поломкой» при оценке ремонта
MAINTENANCE_WORDS = (
    "менял",
    "меняли",
    "замен",
    "поменя",
    "новый",
    "новая",
    "новые",
    "то ",
    "техосмотр",
    "обслужив",
    "сервис",
    "оригинал",
    "комплект",
)

PROBLEM_HINTS = (
    "стук",
    "стучит",
    "течь",
    "течёт",
    "течет",
    "гул",
    "скрип",
    "рывк",
    "не работает",
    "ошибк",
    "горит",
    "требует ремонт",
    "нужен ремонт",
    "битый",
    "битая",
    "крашен",
    "вмятин",
    "ржавчин",
    "корроз",
    "дымит",
    "перегрев",
)


def _load_json(name: str) -> dict:
    with open(DATA_DIR / name, encoding="utf-8") as f:
        return json.load(f)


def _normalize_brand(brand: str | None) -> str:
    if not brand:
        return ""
    return brand.lower().replace(" ", "-").split("-")[0]


def _model_weak_points(brand: str | None) -> list[str]:
    data = _load_json("common_issues.json")
    points = list(data.get("default", []))
    key = _normalize_brand(brand)
    brands = data.get("brands", {})
    for bkey, issues in brands.items():
        if bkey in (key, (brand or "").lower()):
            points.extend(issues)
    return points


def _vehicle_age_years(year: int | None, ref_year: int = 2026) -> int | None:
    if not year:
        return None
    return max(1, ref_year - year)


def _expected_mileage(year: int | None, ref_year: int = 2026) -> int | None:
    age = _vehicle_age_years(year, ref_year)
    if age is None:
        return None
    return age * KM_PER_YEAR_NORM


def _mileage_year_ratio(km: int | None, year: int | None) -> float | None:
    if not km or not year:
        return None
    expected = _expected_mileage(year)
    if not expected:
        return None
    return km / expected


def _mileage_year_risk(
    km: int | None,
    year: int | None,
    maintenance_score: int,
) -> RiskItem | None:
    """Один риск по пробегу: сравнение с нормой для года, не абсолютные пороги."""
    if not km:
        return None
    ratio = _mileage_year_ratio(km, year)
    age = _vehicle_age_years(year)

    if ratio is not None:
        if ratio <= 1.15 and km < 220_000:
            return RiskItem(
                title="Пробег для года",
                severity="low",
                description=(
                    f"Пробег {km:,} км примерно в норме для возраста авто "
                    f"(~{int(ratio * 100)}% от ожидаемого)".replace(",", " ")
                ),
            )
        if ratio <= MILEAGE_RATIO_CAUTION:
            return RiskItem(
                title="Пробег для года",
                severity="low",
                description=(
                    f"Пробег {km:,} км умеренный для года выпуска — "
                    "важнее история ТО и заявленные замены".replace(",", " ")
                ),
            )
        if ratio <= MILEAGE_RATIO_HIGH:
            sev = "medium" if maintenance_score < 2 else "low"
            return RiskItem(
                title="Пробег для года",
                severity=sev,
                description=(
                    f"Пробег {km:,} км выше среднего для {age} лет "
                    f"(~{int(ratio * 100)}% от типичного) — проверьте износ на осмотре".replace(",", " ")
                ),
            )
        return RiskItem(
            title="Пробег для года",
            severity="medium",
            description=(
                f"Пробег {km:,} км заметно выше нормы для года "
                f"(~{int(ratio * 100)}%) — без подтверждённого ТО осторожнее".replace(",", " ")
            ),
        )

    if km >= 280_000:
        return RiskItem(
            title="Пробег",
            severity="medium",
            description="Очень большой пробег — нужны чеки ТО и диагностика агрегатов",
        )
    if km >= 220_000:
        return RiskItem(
            title="Пробег",
            severity="low",
            description="Высокий пробег — уточните, что уже меняли и когда было последнее ТО",
        )
    return None


def _maintenance_score(repairs: list[str], description: str | None) -> int:
    """0–4: насколько продавец описал обслуживание (снижает штраф за пробег/ремонт)."""
    score = 0
    if len(repairs) >= 1:
        score += 1
    if len(repairs) >= 3:
        score += 1
    if len(repairs) >= 5:
        score += 1
    text = (description or "").lower()
    if any(w in text for w in MAINTENANCE_WORDS):
        score += 1
    if any(
        w in text
        for w in ("регулярн", "полное то", "у официал", "сервисная книж", "все то")
    ):
        score += 1
    return min(4, score)


def _description_has_problems(description: str | None) -> bool:
    if not description:
        return False
    low = description.lower()
    return any(h in low for h in PROBLEM_HINTS)


def _filter_weak_points(
    points: list[str],
    mileage_km: int | None,
    year: int | None,
) -> list[str]:
    ratio = _mileage_year_ratio(mileage_km, year)
    out: list[str] = []
    for p in points:
        low = p.lower()
        if "пробег" in low and ratio is not None and ratio < MILEAGE_RATIO_CAUTION:
            continue
        out.append(p)
    return out


def _estimate_from_text(text: str) -> list[RepairLine]:
    data = _load_json("repair_costs.json")
    text_l = text.lower()
    lines: list[RepairLine] = []
    seen: set[str] = set()

    for item in data["items"]:
        if any(kw in text_l for kw in item["keywords"]):
            cat = item["category"]
            if cat in seen:
                continue
            seen.add(cat)
            lines.append(
                RepairLine(
                    category=cat,
                    description=f"По признакам в описании: {cat.lower()}",
                    min_rub=item["min"],
                    max_rub=item["max"],
                )
            )

    if not lines and text.strip():
        d = data["default_line"]
        lines.append(
            RepairLine(
                category=d["category"],
                description="Нераспознанные дефекты — ориентировочная оценка",
                min_rub=d["min"],
                max_rub=d["max"],
            )
        )
    return lines


def _risks_from_defects(
    defects: str | None,
    vehicle: VehicleInput,
    weak_points: list[str],
    maintenance_score: int,
) -> list[RiskItem]:
    risks: list[RiskItem] = []

    for note in weak_points[:4]:
        risks.append(
            RiskItem(
                title="Типичная слабость модели",
                severity="low",
                description=note,
            )
        )

    mileage_risk = _mileage_year_risk(
        vehicle.mileage_km, vehicle.year, maintenance_score
    )
    if mileage_risk:
        risks.append(mileage_risk)

    if vehicle.year and vehicle.year < 2005:
        risks.append(
            RiskItem(
                title="Возраст автомобиля",
                severity="low",
                description="Авто 20+ лет — проверьте коррозию и состояние агрегатов на осмотре",
            )
        )
    elif vehicle.year and vehicle.year < 2010 and maintenance_score < 2:
        risks.append(
            RiskItem(
                title="Возраст автомобиля",
                severity="low",
                description="Возраст 15+ лет — важны свежие замены и подтверждённое ТО",
            )
        )

    if defects:
        for line in _estimate_from_text(defects):
            risks.append(
                RiskItem(
                    title=line.category,
                    severity="high" if line.max_rub > 100000 else "medium",
                    description=line.description,
                    estimated_cost_min=line.min_rub,
                    estimated_cost_max=line.max_rub,
                )
            )

    ratio = _mileage_year_ratio(vehicle.mileage_km, vehicle.year)
    if (
        vehicle.price_rub
        and vehicle.mileage_km
        and vehicle.price_rub > 1_500_000
        and (ratio is None or ratio > MILEAGE_RATIO_HIGH)
        and vehicle.mileage_km > 220_000
        and maintenance_score < 2
    ):
        risks.append(
            RiskItem(
                title="Цена vs пробег",
                severity="medium",
                description="Цена высокая при пробеге выше нормы для года — торгуйтесь или требуйте ТО",
            )
        )

    return risks[:12]


def _risks_from_listing_repairs(repairs: list[str]) -> list[RiskItem]:
    risks: list[RiskItem] = []
    if len(repairs) >= 2:
        risks.append(
            RiskItem(
                title="Обслуживание по объявлению",
                severity="low",
                description=(
                    f"Продавец указал {len(repairs)} работ/замен — "
                    "сверьте чеки и даты; это плюс при оценке"
                ),
            )
        )
    for line in repairs[:6]:
        risks.append(
            RiskItem(
                title="Заявлено в объявлении",
                severity="low",
                description=(
                    f"«{line}» — проверьте документы, даты и качество работ на осмотре"
                ),
            )
        )
    return risks


def _risks_from_preferences(
    preferences: str | None,
    vehicle: VehicleInput,
) -> list[RiskItem]:
    notes = analyze_user_preferences(preferences, vehicle.brand, vehicle.model)
    return [
        RiskItem(
            title="Ваши пожелания",
            severity="low",
            description=note,
        )
        for note in notes
    ]


def _adjust_repairs_for_claims(
    repair_lines: list[RepairLine],
    repairs: list[str],
) -> list[RepairLine]:
    claimed = repair_categories_claimed(repairs)
    if not claimed:
        return repair_lines
    out: list[RepairLine] = []
    for line in repair_lines:
        if line.category in claimed:
            out.append(
                line.model_copy(
                    update={
                        "min_rub": int(line.min_rub * 0.5),
                        "max_rub": int(line.max_rub * 0.6),
                        "description": (
                            f"{line.description}. По объявлению узел меняли — "
                            "подтвердите на осмотре; оценка снижена"
                        ),
                    }
                )
            )
        else:
            out.append(line)
    return out


def _substantive_risks(risks: list[RiskItem]) -> list[RiskItem]:
    return [r for r in risks if r.title not in INFO_RISK_TITLES]


def _severity_rank(value: str) -> int:
    return {"low": 1, "medium": 2, "high": 3}.get(value, 1)


def _snippet(text: str | None, limit: int = 180) -> str | None:
    if not text:
        return None
    clean = " ".join(text.split()).strip()
    if not clean:
        return None
    if len(clean) <= limit:
        return clean
    return f"{clean[: limit - 1]}…"


def _repair_action(category: str) -> str:
    actions = {
        "КПП": "Сделайте профильную диагностику трансмиссии и запросите дефектовку до покупки",
        "Двигатель": "Проверьте компрессию, утечки и историю ТО; зафиксируйте смету заранее",
        "Подвеска": "Проведите осмотр на подъемнике и проверьте люфты/течь амортизаторов",
        "Тормоза": "Проверьте остаток колодок/дисков и учтите замену расходников в торге",
        "Кузов": "Промерьте ЛКП и проверьте скрытые зоны на следы ремонта/коррозии",
    }
    return actions.get(
        category,
        "Уточните дефект на диагностике и запросите смету у профильного сервиса",
    )


def _enrich_risks_with_precision(
    risks: list[RiskItem],
    defects: str | None,
    repairs: list[str],
    weak_points: list[str],
    vehicle: VehicleInput,
) -> list[RiskItem]:
    defects_snippet = _snippet(defects)
    repairs_text = "; ".join(repairs[:3])
    enriched: list[RiskItem] = []
    for risk in risks:
        evidence: list[EvidenceItem] = list(risk.evidence)
        rationale_bits: list[str] = []

        if defects_snippet and risk.title not in INFO_RISK_TITLES:
            evidence.append(
                EvidenceItem(
                    source="defects",
                    signal="reported_defects",
                    details=defects_snippet,
                )
            )
            rationale_bits.append("учтены заявленные/обнаруженные дефекты")

        if repairs_text:
            evidence.append(
                EvidenceItem(
                    source="listing_repairs",
                    signal="seller_claims",
                    details=repairs_text,
                )
            )
            rationale_bits.append("учтены работы, заявленные в объявлении")

        if weak_points and risk.title in {"Типичная слабость модели", "КПП", "Двигатель"}:
            evidence.append(
                EvidenceItem(
                    source="model_weak_points",
                    signal="known_weakness",
                    details=weak_points[0],
                )
            )
            rationale_bits.append("учтены типовые слабые места модели")

        if vehicle.price_rub:
            evidence.append(
                EvidenceItem(
                    source="vehicle",
                    signal="price_context",
                    value=vehicle.price_rub,
                    details="Цена влияет на приоритет торга и долю риска в бюджете",
                )
            )

        priority = (
            RiskSeverityEnum.high
            if _severity_rank(risk.severity) >= 3
            else risk.severity
        )
        confidence = risk.confidence or 70
        if defects_snippet and risk.title not in INFO_RISK_TITLES:
            confidence = max(confidence, 82)
        if risk.title in INFO_RISK_TITLES:
            confidence = min(confidence, 72)

        enriched.append(
            risk.model_copy(
                update={
                    "priority": priority,
                    "confidence": max(45, min(99, confidence)),
                    "rationale": (
                        "; ".join(dict.fromkeys(rationale_bits))
                        if rationale_bits
                        else risk.rationale
                        or "Риск сформирован по базовой модели оценки и входным данным объявления"
                    ),
                    "evidence": evidence[:5],
                    "action": risk.action
                    or "Сверьте факт дефекта на осмотре и используйте оценку риска для аргумента торга",
                }
            )
        )
    return enriched


def _enrich_repair_lines_with_precision(
    repair_lines: list[RepairLine],
    defects: str | None,
    repairs: list[str],
) -> list[RepairLine]:
    defects_snippet = _snippet(defects)
    repairs_text = "; ".join(repairs[:3]) if repairs else None
    enriched: list[RepairLine] = []
    for line in repair_lines:
        evidence: list[EvidenceItem] = list(line.evidence)
        if defects_snippet:
            evidence.append(
                EvidenceItem(
                    source="defects",
                    signal="repair_trigger",
                    details=defects_snippet,
                )
            )
        if repairs_text:
            evidence.append(
                EvidenceItem(
                    source="listing_repairs",
                    signal="possible_prior_work",
                    details=repairs_text,
                )
            )

        if line.max_rub >= 150_000:
            priority = RiskSeverityEnum.high
        elif line.max_rub >= 60_000:
            priority = RiskSeverityEnum.medium
        else:
            priority = RiskSeverityEnum.low
        confidence = 85 if defects_snippet else 70

        enriched.append(
            line.model_copy(
                update={
                    "priority": priority,
                    "confidence": confidence,
                    "rationale": (
                        "Оценка рассчитана по дефектам, тексту объявления и типовым диапазонам категории"
                    ),
                    "evidence": evidence[:5],
                    "action": _repair_action(line.category),
                }
            )
        )
    return enriched


def build_replacement_suggestions(
    repair_lines: list[RepairLine],
    parts_pricing: list[PartPriceBlock],
) -> list[ReplacementPartSuggestion]:
    suggestions: list[ReplacementPartSuggestion] = []
    seen: set[tuple[str, str]] = set()
    for block in parts_pricing:
        key = (block.category, block.part_name.lower().strip())
        if key in seen:
            continue
        seen.add(key)
        related = next((r for r in repair_lines if r.category == block.category), None)
        priority = (
            related.priority
            if related and related.priority
            else RiskSeverityEnum.medium
        )
        confidence = related.confidence if related and related.confidence is not None else 70
        offer_urls = [o.url for o in block.avito_offers[:3]]
        offer_cards = block.avito_offers[:3]
        source_platforms = sorted(
            {
                (urlparse(url).netloc.lower().replace("www.", "") or "unknown")
                for url in offer_urls
                if url
            }
        )
        search_url = block.search_url or build_avito_search_url(block.search_query)
        availability = "available" if offer_urls else "limited"
        actions = (
            [
                "Сравните минимум 2-3 предложения по цене и состоянию",
                "Уточните совместимость по VIN/каталожному номеру",
                "Зафиксируйте стоимость запчасти в торге",
            ]
            if offer_urls
            else [
                "Откройте поисковую ссылку и соберите 2-3 актуальных предложения",
                "Проверьте совместимость с вашим VIN",
            ]
        )
        suggestions.append(
            ReplacementPartSuggestion(
                category=block.category,
                part_name=block.part_name,
                search_query=block.search_query,
                search_url=search_url,
                rationale=(
                    related.rationale
                    if related and related.rationale
                    else "Подбор запчасти по категории риска и расчету ремонтного бюджета"
                ),
                availability=availability,
                offer_urls=offer_urls,
                source_platforms=source_platforms,
                price_range_rub=(
                    f"{(block.estimate_min or block.avito_min or 0):,}–{(block.estimate_max or block.avito_max or 0):,} ₽".replace(",", " ")
                    if (block.estimate_min or block.avito_min) and (block.estimate_max or block.avito_max)
                    else None
                ),
                suggested_actions=actions,
                confidence=confidence,
                priority=priority,
                offer_cards=offer_cards,
                price_min_rub=block.estimate_min or block.avito_min or block.market_min,
                price_max_rub=block.estimate_max or block.avito_max or block.market_max,
                marketplace_links=list(dict.fromkeys([search_url, *offer_urls])),
            )
        )
    return suggestions


def _calc_verdict(
    risks: list[RiskItem],
    repair_max: int,
    price: int | None,
    post: bool = False,
    maintenance_score: int = 0,
    has_defects: bool = False,
) -> VerdictEnum:
    substantive = _substantive_risks(risks)
    high = sum(1 for r in substantive if r.severity == "high")
    medium = sum(1 for r in substantive if r.severity == "medium")

    skip_repair = 400_000 if maintenance_score >= 3 else 350_000
    caution_repair = 180_000 if maintenance_score >= 2 else 140_000

    if high >= 3 or (high >= 2 and repair_max > skip_repair):
        return VerdictEnum.skip
    if high >= 2 or repair_max > skip_repair:
        return VerdictEnum.caution
    if high >= 1 or medium >= 3 or repair_max > caution_repair:
        return VerdictEnum.caution
    if post and has_defects and repair_max > 100_000:
        return VerdictEnum.caution
    if post and repair_max > 80_000 and maintenance_score < 2:
        return VerdictEnum.caution

    if price and has_defects and repair_max > price * 0.4:
        return VerdictEnum.skip
    if price and has_defects and repair_max > price * 0.25:
        return VerdictEnum.caution

    return VerdictEnum.worth_looking


def _risk_score(risks: list[RiskItem], repair_max: int, price: int | None) -> int:
    score = 0
    for risk in risks:
        if risk.title in INFO_RISK_TITLES:
            continue
        if risk.severity == "high":
            score += 22
        elif risk.severity == "medium":
            score += 11
        else:
            score += 5
    if price and price > 0 and repair_max > 0:
        score += min(35, int((repair_max / price) * 55))
    elif repair_max > 0:
        score += min(25, repair_max // 20_000)
    return min(100, max(0, score))


def _final_recommendation(
    verdict: VerdictEnum,
    risk_score: int,
    repair_max: int,
    price: int | None,
) -> FinalRecommendationEnum:
    if verdict == VerdictEnum.skip or risk_score >= 75:
        return FinalRecommendationEnum.REJECT
    if verdict == VerdictEnum.caution or risk_score >= 40:
        return FinalRecommendationEnum.CAUTIOUS
    if price and repair_max > int(price * 0.2):
        return FinalRecommendationEnum.CAUTIOUS
    return FinalRecommendationEnum.BUY_WITH_CONFIDENCE


def _resale_economics(
    vehicle: VehicleInput,
    repair_min: int,
    repair_max: int,
    target_resale: int | None,
) -> ResaleEconomics | None:
    if not vehicle.price_rub:
        return None
    mid = (repair_min + repair_max) // 2
    target = target_resale or int(vehicle.price_rub * 1.12)
    margin = target - vehicle.price_rub - mid
    pct = (margin / vehicle.price_rub * 100) if vehicle.price_rub else None
    if margin < 0:
        comment = "Сделка убыточна с учётом ориентировочного ремонта"
    elif margin < 50_000:
        comment = "Маржа низкая — учтите время продажи и налоги"
    else:
        comment = "Потенциально интересная сделка для перепродажи"
    return ResaleEconomics(
        purchase_price=vehicle.price_rub,
        repair_mid=mid,
        target_resale=target,
        estimated_margin=margin,
        margin_percent=round(pct, 1) if pct is not None else None,
        comment=comment,
    )


def build_analysis_report(
    vehicle: VehicleInput,
    defects: str | None = None,
    user_preferences: str | None = None,
    listing_repairs: list[str] | None = None,
    is_reseller: bool = False,
    target_resale_price: int | None = None,
    post_inspection: bool = False,
) -> AnalysisReport:
    weak = _filter_weak_points(
        _model_weak_points(vehicle.brand),
        vehicle.mileage_km,
        vehicle.year,
    )
    checklist = build_checklist(vehicle.transmission)

    repairs = list(listing_repairs or [])
    if not repairs and vehicle.description:
        repairs = extract_listing_repairs(vehicle.description)

    maintenance_score = _maintenance_score(repairs, vehicle.description)
    has_defects = bool(defects and defects.strip())

    risks = _risks_from_defects(defects, vehicle, weak, maintenance_score)
    risks.extend(_risks_from_listing_repairs(repairs))
    risks.extend(_risks_from_preferences(user_preferences, vehicle))
    risks = risks[:16]
    risks = _enrich_risks_with_precision(risks, defects, repairs, weak, vehicle)

    repair_source = defects or ""
    if _description_has_problems(vehicle.description):
        repair_source = f"{repair_source} {vehicle.description}".strip()
    repair_lines = _estimate_from_text(repair_source) if repair_source.strip() else []
    repair_lines = _adjust_repairs_for_claims(repair_lines, repairs)
    if maintenance_score >= 2 and repair_lines:
        repair_lines = [
            line.model_copy(
                update={
                    "min_rub": int(line.min_rub * 0.7),
                    "max_rub": int(line.max_rub * 0.75),
                }
            )
            for line in repair_lines
        ]
    repair_lines = _enrich_repair_lines_with_precision(repair_lines, defects, repairs)
    repair_min = sum(l.min_rub for l in repair_lines) if repair_lines else 0
    repair_max = sum(l.max_rub for l in repair_lines) if repair_lines else 0

    verdict = _calc_verdict(
        risks,
        repair_max,
        vehicle.price_rub,
        post=post_inspection,
        maintenance_score=maintenance_score,
        has_defects=has_defects,
    )
    risk_score = _risk_score(risks, repair_max, vehicle.price_rub)
    recommendation = _final_recommendation(
        verdict, risk_score, repair_max, vehicle.price_rub
    )

    summary_parts = [
        f"{vehicle.brand or 'Авто'} {vehicle.model or ''}".strip(),
    ]
    if vehicle.year:
        summary_parts.append(str(vehicle.year))
    if vehicle.mileage_km:
        summary_parts.append(f"пробег {vehicle.mileage_km:,} км".replace(",", " "))
    if vehicle.price_rub:
        summary_parts.append(f"цена {vehicle.price_rub:,} ₽".replace(",", " "))
    if user_preferences and user_preferences.strip():
        summary_parts.append("учтены ваши пожелания")
    if repairs:
        summary_parts.append(f"в объявлении указано {len(repairs)} работ/замен")
    ratio = _mileage_year_ratio(vehicle.mileage_km, vehicle.year)
    if ratio is not None and ratio <= MILEAGE_RATIO_CAUTION:
        summary_parts.append("пробег для года в норме")
    elif maintenance_score >= 2:
        summary_parts.append("учтено заявленное ТО/замены")
    passport_parts: list[str] = []
    if vehicle.year:
        passport_parts.append(f"год {vehicle.year}")
    if vehicle.mileage_km:
        passport_parts.append(f"пробег {vehicle.mileage_km:,} км".replace(",", " "))
    if vehicle.price_rub:
        passport_parts.append(f"цена {vehicle.price_rub:,} ₽".replace(",", " "))
    if vehicle.engine:
        passport_parts.append(f"двигатель {vehicle.engine}")
    if vehicle.transmission:
        passport_parts.append(f"КПП {vehicle.transmission}")
    if vehicle.drive:
        passport_parts.append(f"привод {vehicle.drive}")
    passport_sentence = (
        "Паспорт авто: " + "; ".join(passport_parts) + "."
        if passport_parts
        else "Паспорт авто: данных недостаточно."
    )
    summary = ". ".join(summary_parts) + f". {passport_sentence} {VERDICT_LABELS[verdict]}."
    analysis_rationale: list[str] = []
    if defects and defects.strip():
        analysis_rationale.append(
            f"Дефекты/наблюдения учтены в расчете рисков и ремонта: {_snippet(defects, 220)}"
        )
    if repairs:
        analysis_rationale.append(
            f"Текст объявления и заявленные работы учтены: {', '.join(repairs[:4])}"
        )
    if weak:
        analysis_rationale.append(
            f"Типовые слабые места модели учтены: {', '.join(weak[:3])}"
        )
    if not analysis_rationale:
        analysis_rationale.append(
            "Оценка построена на характеристиках авто и типовых рыночных диапазонах ремонта"
        )
    analysis_rationale.append(
        "Причины решения: оценены severity рисков, бюджет ремонта и evidence из объявления/дефектов"
    )

    resale = None
    if is_reseller:
        resale = _resale_economics(vehicle, repair_min, repair_max, target_resale_price)

    passport_bits: list[str] = []
    if vehicle.brand or vehicle.model:
        passport_bits.append(f"{vehicle.brand or 'Не указана'} {vehicle.model or ''}".strip())
    if vehicle.year:
        passport_bits.append(f"год {vehicle.year}")
    if vehicle.mileage_km:
        passport_bits.append(f"пробег {vehicle.mileage_km:,} км".replace(",", " "))
    if vehicle.price_rub:
        passport_bits.append(f"цена {vehicle.price_rub:,} ₽".replace(",", " "))
    if vehicle.vin:
        passport_bits.append(f"VIN {vehicle.vin}")
    if not passport_bits:
        passport_bits.append("данные по авто частично отсутствуют")

    return AnalysisReport(
        verdict=verdict,
        final_recommendation=recommendation,
        verdict_label=VERDICT_LABELS[verdict],
        summary=summary,
        vehicle_passport_summary="; ".join(passport_bits),
        risk_score=risk_score,
        risks=risks,
        checklist=checklist,
        repair_lines=repair_lines,
        repair_total_min=repair_min,
        repair_total_max=repair_max,
        resale=resale,
        model_weak_points=weak[:6],
        listing_repairs=repairs[:8],
        preference_notes=analyze_user_preferences(
            user_preferences, vehicle.brand, vehicle.model
        ),
        analysis_rationale=analysis_rationale,
        vehicle_passport=VehiclePassport(
            brand=vehicle.brand,
            model=vehicle.model,
            year=vehicle.year,
            mileage_km=vehicle.mileage_km,
            price_rub=vehicle.price_rub,
            engine=vehicle.engine,
            transmission=vehicle.transmission,
            drive=vehicle.drive,
            body_type=vehicle.body_type,
            color=vehicle.color,
            vin=vehicle.vin,
            source_quality="complete"
            if vehicle.brand and vehicle.model and vehicle.year and vehicle.mileage_km
            else "partial",
        ),
        photo_findings=[],
    )


async def maybe_enrich_with_llm(
    report: AnalysisReport,
    vehicle: VehicleInput,
    defects: str | None,
    user_preferences: str | None = None,
    listing_repairs: list[str] | None = None,
) -> AnalysisReport:
    if not settings.llm_enabled:
        # Даже без LLM запускаем market_comparison (он не зависит от ключа)
        try:
            from app.services.market_comparison import get_market_comparison

            if vehicle.brand and vehicle.model and vehicle.price_rub:
                report.market_comparison = await get_market_comparison(vehicle)
        except Exception:
            pass
        return report

    try:
        from app.services.llm import enrich_report_with_llm

        report = await enrich_report_with_llm(
            report, vehicle, defects, user_preferences, listing_repairs
        )
        # Пересчёт итогов после LLM-обогащения. Без этого отчёт противоречит
        # сам себе: «Рекомендуем, риск 0%» рядом со списком P1-рисков.
        #
        # LLM-риски (evidence.source == "llm") — типовые слабые места модели,
        # а не подтверждённые дефекты, поэтому они дают приглушённый вклад
        # с потолком 30 пунктов; подтверждённые риски считаются полным весом.
        confirmed = [
            r for r in report.risks
            if not any(e.source == "llm" for e in (r.evidence or []))
        ]
        speculative_weights = {"high": 6, "medium": 3, "low": 1}
        speculative_score = min(30, sum(
            speculative_weights.get(str(r.severity.value if hasattr(r.severity, "value") else r.severity), 3)
            for r in report.risks
            if any(e.source == "llm" for e in (r.evidence or []))
        ))
        report.risk_score = min(100, _risk_score(
            confirmed, report.repair_total_max, vehicle.price_rub
        ) + speculative_score)
        if report.risk_score >= 75:
            report.verdict = VerdictEnum.skip
        elif report.risk_score >= 40 and report.verdict == VerdictEnum.worth_looking:
            report.verdict = VerdictEnum.caution
        report.verdict_label = VERDICT_LABELS[report.verdict]
        report.final_recommendation = _final_recommendation(
            report.verdict, report.risk_score, report.repair_total_max, vehicle.price_rub
        )
    except Exception:
        pass

    try:
        from app.services.negotiation import generate_negotiation_tips

        report.negotiation_tips = await generate_negotiation_tips(report, vehicle)
    except Exception:
        pass

    try:
        from app.services.market_comparison import get_market_comparison

        if vehicle.brand and vehicle.model and vehicle.price_rub:
            report.market_comparison = await get_market_comparison(vehicle)
    except Exception:
        pass

    return report


def format_report_text(report: AnalysisReport, title: str = "Анализ") -> str:
    lines = [
        f"📋 <b>{title}</b>",
        "",
        f"<b>{report.verdict_label}</b>",
        report.summary,
        "",
        "<b>⚠️ Риски</b>",
    ]
    if not report.risks:
        lines.append("• Явных рисков по вводу не найдено — всё равно пройдите чеклист")
    for r in report.risks[:8]:
        cost = ""
        if r.estimated_cost_min is not None:
            cost = f" ({r.estimated_cost_min:,}–{r.estimated_cost_max:,} ₽)".replace(",", " ")
        lines.append(
            f"• [{r.severity}|prio:{r.priority}|conf:{r.confidence}%] {r.title}: {r.description}{cost}"
        )
        if r.rationale:
            lines.append(f"  Почему: {r.rationale}")
        if r.evidence:
            ev = r.evidence[0]
            details = ev.details or str(ev.value or "")
            if details:
                lines.append(f"  Доказательство ({ev.source}/{ev.signal}): {details}")

    if report.preference_notes:
        lines.extend(["", "<b>🎯 Ваши пожелания</b>"])
        for p in report.preference_notes[:4]:
            lines.append(f"• {p}")

    if report.listing_repairs:
        lines.extend(["", "<b>📝 Указано в объявлении</b>"])
        for p in report.listing_repairs[:4]:
            lines.append(f"• {p}")

    if report.model_weak_points:
        lines.extend(["", "<b>🔧 Слабые места модели</b>"])
        for p in report.model_weak_points[:4]:
            lines.append(f"• {p}")

    lines.extend(
        [
            "",
            f"<b>💰 Ремонт (ориентир)</b>: {report.repair_total_min:,}–{report.repair_total_max:,} ₽".replace(
                ",", " "
            ),
        ]
    )

    if report.vin_summary:
        lines.extend(["", f"<b>🔑 VIN</b>: {report.vin_summary}"])

    if report.parts_pricing:
        lines.extend(["", "<b>🔩 Запчасти (ориентир)</b>"])
        for block in report.parts_pricing[:4]:
            est = ""
            if block.estimate_min and block.estimate_max:
                est = f" ~{block.estimate_min:,}–{block.estimate_max:,} ₽".replace(",", " ")
            lines.append(f"• {block.part_name}{est}")
            if block.avito_offers:
                o = block.avito_offers[0]
                lines.append(f"  <a href=\"{o.url}\">Авито</a> от {o.price_rub:,} ₽".replace(",", " "))
            elif block.search_url:
                lines.append(f"  <a href=\"{block.search_url}\">Поиск на Авито</a>")

    if report.replacement_suggestions:
        lines.extend(["", "<b>🧩 Рекомендованные замены</b>"])
        for item in report.replacement_suggestions[:4]:
            lines.append(
                f"• {item.part_name} [{item.priority}|conf:{item.confidence}%] — {item.rationale}"
            )
            if item.offer_urls:
                lines.append(f"  <a href=\"{item.offer_urls[0]}\">Открыть предложение</a>")
            elif item.search_url:
                lines.append(f"  <a href=\"{item.search_url}\">Открыть поиск</a>")

    if report.resale:
        r = report.resale
        lines.extend(
            [
                "",
                "<b>📈 Перепродажа</b>",
                f"Покупка: {r.purchase_price:,} ₽, ремонт ~{r.repair_mid:,} ₽".replace(",", " "),
                f"Цель продажи: {r.target_resale:,} ₽, маржа ~{r.estimated_margin:,} ₽".replace(
                    ",", " "
                ),
                r.comment,
            ]
        )

    lines.extend(["", "<b>✅ Чеклист осмотра</b> (сокращённо)"])
    for i, c in enumerate(report.checklist[:5], 1):
        lines.append(f"{i}. <b>{c.zone}</b>: {c.title}")
    lines.append("… полный чеклист — в карточке проверки /history")

    return "\n".join(lines)


def format_checklist_full(report: AnalysisReport) -> str:
    parts = ["<b>📋 Полный чеклист осмотра</b>", ""]
    for i, c in enumerate(report.checklist, 1):
        tools = ", ".join(c.tools) if c.tools else "—"
        flags = "; ".join(c.red_flags) if c.red_flags else "—"
        parts.extend(
            [
                f"<b>{i}. {c.zone} — {c.title}</b>",
                f"Как проверять: {c.how_to_check}",
                f"Инструменты: {tools}",
                f"Тревожные признаки: {flags}",
                "",
            ]
        )
    return "\n".join(parts)

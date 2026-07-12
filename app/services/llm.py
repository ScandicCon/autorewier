import json

from openai import AsyncOpenAI

from app.config import settings
from app.schemas import EvidenceItem, AnalysisReport, RiskItem, VehicleInput


def _openrouter_client() -> AsyncOpenAI:
    headers: dict[str, str] = {}
    if settings.openrouter_site_url.strip():
        headers["HTTP-Referer"] = settings.openrouter_site_url.strip()
    if settings.openrouter_app_name.strip():
        headers["X-Title"] = settings.openrouter_app_name.strip()

    return AsyncOpenAI(
        api_key=settings.openrouter_api_key,
        base_url=settings.openrouter_base_url.rstrip("/"),
        default_headers=headers or None,
    )


async def enrich_report_with_llm(
    report: AnalysisReport,
    vehicle: VehicleInput,
    defects: str | None,
    user_preferences: str | None = None,
    listing_repairs: list[str] | None = None,
) -> AnalysisReport:
    client = _openrouter_client()
    prompt = {
        "vehicle": vehicle.model_dump(exclude_none=True),
        "defects": defects,
        "user_preferences": user_preferences,
        "listing_repairs": listing_repairs or [],
        "existing_risks": [r.model_dump() for r in report.risks[:6]],
    }
    response = await client.chat.completions.create(
        model=settings.openrouter_model,
        messages=[
            {
                "role": "system",
                "content": (
                    "Ты — топовый автоподборщик-эксперт в РФ, который реально спас сотни покупателей "
                    "от плохих сделок. Дай ОСТРЫЕ, КОНКРЕТНЫЕ риски именно для этой марки/модели/"
                    "двигателя/КПП/года и пробега — реальные слабые места и типичные болячки этой "
                    "конкретной машины, а не общие фразы. "
                    "Год и пробег сами по себе не повод для severity high — важнее ТО, замены и "
                    "заявленные дефекты. severity high только при явных проблемах "
                    "(ДТП, течи, стуки, перегрев, скрученный пробег, юридические риски). "
                    "Каждый риск пиши так: в чём проблема именно у этой модели + ЧТО КОНКРЕТНО "
                    "проверить на осмотре/диагностике и на что это влияет в деньгах. "
                    "Запрещены общие фразы вроде 'проверьте лично', 'типичная слабость модели', "
                    "'возможны скрытые дефекты' — только конкретика по этой машине. "
                    "Учитывай пожелания покупателя и заявленные замены. "
                    "Дай 3-5 таких рисков. Ответ только JSON: "
                    '{"extra_risks":[{"title":"коротко и по делу","severity":"low|medium|high",'
                    '"description":"проблема именно у этой модели + что конкретно проверить"}],'
                    '"summary_addition":"1-2 предложения: чёткий вывод брать/осторожно/не брать '
                    'и на что смотреть в первую очередь"}'
                ),
            },
            {"role": "user", "content": json.dumps(prompt, ensure_ascii=False)},
        ],
        temperature=0.3,
    )
    # Учёт себестоимости: сколько токенов реально потратила проверка.
    from app.services.cost_tracking import record_llm
    usage = getattr(response, "usage", None)
    record_llm(
        getattr(usage, "prompt_tokens", 0) if usage else 0,
        getattr(usage, "completion_tokens", 0) if usage else 0,
    )
    raw = response.choices[0].message.content or "{}"
    raw = raw.strip()
    if raw.startswith("```"):
        raw = raw.split("\n", 1)[-1].rsplit("```", 1)[0]
    data = json.loads(raw)

    for item in data.get("extra_risks", []):
        report.risks.append(
            RiskItem(
                title=item.get("title", "AI"),
                severity=item.get("severity", "medium"),
                description=item.get("description", ""),
                # Метка источника: типовой риск модели от нейросети, не
                # подтверждённый дефект. Учитывается в risk_score с меньшим
                # весом (см. maybe_enrich_with_llm).
                evidence=[
                    EvidenceItem(
                        source="llm",
                        signal="model_pattern",
                        details="Типовой риск модели — проверить при осмотре",
                    )
                ],
            )
        )
    if add := data.get("summary_addition"):
        report.summary = f"{report.summary} {add}"
    return report

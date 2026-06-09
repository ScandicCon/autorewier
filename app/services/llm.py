import json

from openai import AsyncOpenAI

from app.config import settings
from app.schemas import AnalysisReport, RiskItem, VehicleInput


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
                    "Ты эксперт по оценке подержанных авто в РФ. "
                    "Год и пробег сами по себе не повод для severity high — важнее ТО и замены из объявления. "
                    "severity high только при явных дефектах (ДТП, течи, стуки, юридические риски). "
                    "Учти пожелания покупателя и заявленные замены/ремонт. "
                    "Дополни анализ 2-4 конкретными рисками. Ответ только JSON: "
                    '{"extra_risks":[{"title":"","severity":"low|medium|high","description":""}],'
                    '"summary_addition":"одно предложение"}'
                ),
            },
            {"role": "user", "content": json.dumps(prompt, ensure_ascii=False)},
        ],
        temperature=0.3,
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
            )
        )
    if add := data.get("summary_addition"):
        report.summary = f"{report.summary} {add}"
    return report

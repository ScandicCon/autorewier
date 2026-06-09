"""Генерация PDF-отчёта об осмотре автомобиля через ReportLab."""
from __future__ import annotations

import logging
from io import BytesIO
from pathlib import Path

from reportlab.lib import colors
from reportlab.lib.pagesizes import A4
from reportlab.lib.styles import getSampleStyleSheet, ParagraphStyle
from reportlab.lib.units import cm
from reportlab.platypus import (
    Paragraph,
    SimpleDocTemplate,
    Spacer,
    Table,
    TableStyle,
)
from reportlab.pdfbase import pdfmetrics
from reportlab.pdfbase.ttfonts import TTFont

from app.schemas import AnalysisReport

logger = logging.getLogger(__name__)

# --------------------------------------------------------------------------- #
# Шрифты
# --------------------------------------------------------------------------- #

_FONT_DIR = Path(__file__).resolve().parent.parent / "data" / "fonts"
_FONT_REGISTERED = False


def _ensure_fonts() -> None:
    global _FONT_REGISTERED
    if _FONT_REGISTERED:
        return

    regular = _FONT_DIR / "DejaVuSans.ttf"
    bold = _FONT_DIR / "DejaVuSans-Bold.ttf"

    if regular.exists() and bold.exists():
        pdfmetrics.registerFont(TTFont("DejaVuSans", str(regular)))
        pdfmetrics.registerFont(TTFont("DejaVuSans-Bold", str(bold)))
        _FONT_REGISTERED = True
        return

    # Fallback: попробуем системные пути Windows/Linux
    candidates_regular = [
        Path("C:/Windows/Fonts/arial.ttf"),
        Path("/usr/share/fonts/truetype/dejavu/DejaVuSans.ttf"),
        Path("/usr/share/fonts/TTF/DejaVuSans.ttf"),
    ]
    candidates_bold = [
        Path("C:/Windows/Fonts/arialbd.ttf"),
        Path("/usr/share/fonts/truetype/dejavu/DejaVuSans-Bold.ttf"),
        Path("/usr/share/fonts/TTF/DejaVuSans-Bold.ttf"),
    ]

    reg_path = next((p for p in candidates_regular if p.exists()), None)
    bold_path = next((p for p in candidates_bold if p.exists()), None)

    if reg_path and bold_path:
        font_name = "DejaVuSans" if "DejaVu" in str(reg_path) else "CustomFont"
        bold_name = font_name + "-Bold"
        pdfmetrics.registerFont(TTFont(font_name, str(reg_path)))
        pdfmetrics.registerFont(TTFont(bold_name, str(bold_path)))
        # Нормализуем к единому имени
        if font_name != "DejaVuSans":
            # Регистрируем под нашим именем-алиасом
            pdfmetrics.registerFont(TTFont("DejaVuSans", str(reg_path)))
            pdfmetrics.registerFont(TTFont("DejaVuSans-Bold", str(bold_path)))
        _FONT_REGISTERED = True


# --------------------------------------------------------------------------- #
# Стили
# --------------------------------------------------------------------------- #

_SEVERITY_COLORS = {
    "high": colors.HexColor("#c0392b"),
    "medium": colors.HexColor("#e67e22"),
    "low": colors.HexColor("#27ae60"),
}

_VERDICT_COLORS = {
    "worth_looking": colors.HexColor("#27ae60"),
    "caution": colors.HexColor("#e67e22"),
    "skip": colors.HexColor("#c0392b"),
}

_RECOMMENDATION_RU = {
    "BUY_WITH_CONFIDENCE": "Рекомендуется к покупке",
    "CAUTIOUS": "Покупать с осторожностью",
    "REJECT": "Не рекомендуется",
}


def _styles() -> dict:
    """Возвращает словарь именованных стилей ReportLab."""
    _ensure_fonts()
    base = getSampleStyleSheet()

    font = "DejaVuSans" if _FONT_REGISTERED else "Helvetica"
    font_bold = "DejaVuSans-Bold" if _FONT_REGISTERED else "Helvetica-Bold"

    return {
        "title": ParagraphStyle(
            "PDFTitle",
            fontName=font_bold,
            fontSize=16,
            leading=20,
            spaceAfter=6,
            textColor=colors.HexColor("#1a1a2e"),
        ),
        "subtitle": ParagraphStyle(
            "PDFSubtitle",
            fontName=font_bold,
            fontSize=12,
            leading=16,
            spaceAfter=4,
            textColor=colors.HexColor("#2c3e50"),
        ),
        "section": ParagraphStyle(
            "PDFSection",
            fontName=font_bold,
            fontSize=11,
            leading=14,
            spaceBefore=10,
            spaceAfter=4,
            textColor=colors.HexColor("#2c3e50"),
            borderPad=2,
        ),
        "body": ParagraphStyle(
            "PDFBody",
            fontName=font,
            fontSize=9,
            leading=13,
            spaceAfter=2,
        ),
        "bullet": ParagraphStyle(
            "PDFBullet",
            fontName=font,
            fontSize=9,
            leading=13,
            leftIndent=12,
            spaceAfter=2,
            bulletText="•",
        ),
        "small": ParagraphStyle(
            "PDFSmall",
            fontName=font,
            fontSize=8,
            leading=11,
            textColor=colors.HexColor("#7f8c8d"),
        ),
        "verdict_ok": ParagraphStyle(
            "PDFVerdictOk",
            fontName=font_bold,
            fontSize=13,
            leading=17,
            textColor=colors.HexColor("#27ae60"),
        ),
        "verdict_warn": ParagraphStyle(
            "PDFVerdictWarn",
            fontName=font_bold,
            fontSize=13,
            leading=17,
            textColor=colors.HexColor("#e67e22"),
        ),
        "verdict_bad": ParagraphStyle(
            "PDFVerdictBad",
            fontName=font_bold,
            fontSize=13,
            leading=17,
            textColor=colors.HexColor("#c0392b"),
        ),
    }


# --------------------------------------------------------------------------- #
# Вспомогательные функции
# --------------------------------------------------------------------------- #

def _verdict_style_name(verdict: str) -> str:
    if verdict == "worth_looking":
        return "verdict_ok"
    if verdict == "caution":
        return "verdict_warn"
    return "verdict_bad"


def _sep(styles: dict):
    """Горизонтальный разделитель."""
    return Table(
        [[""]],
        colWidths=[17 * cm],
        style=TableStyle([
            ("LINEBELOW", (0, 0), (-1, -1), 0.5, colors.HexColor("#bdc3c7")),
            ("TOPPADDING", (0, 0), (-1, -1), 0),
            ("BOTTOMPADDING", (0, 0), (-1, -1), 4),
        ]),
    )


def _section_header(text: str, styles: dict):
    return Paragraph(text, styles["section"])


def _fmt_rub(val: int | None) -> str:
    if val is None:
        return "—"
    return f"{val:,} ₽".replace(",", " ")


# --------------------------------------------------------------------------- #
# Основная функция генерации PDF
# --------------------------------------------------------------------------- #

def generate_inspection_pdf(report: AnalysisReport, vehicle_label: str) -> bytes:
    """
    Генерирует PDF-отчёт об осмотре авто.

    :param report: AnalysisReport — данные отчёта
    :param vehicle_label: строка вида «Toyota Camry 2019»
    :returns: bytes — содержимое PDF файла
    """
    _ensure_fonts()
    styles = _styles()

    buf = BytesIO()
    doc = SimpleDocTemplate(
        buf,
        pagesize=A4,
        rightMargin=2 * cm,
        leftMargin=2 * cm,
        topMargin=2 * cm,
        bottomMargin=2 * cm,
        title=f"Отчёт об осмотре: {vehicle_label}",
        author="AutoRewier",
    )

    story = []

    # ------------------------------------------------------------------ #
    # 1. Заголовок
    # ------------------------------------------------------------------ #
    story.append(Paragraph("Отчёт об осмотре автомобиля", styles["title"]))
    story.append(Paragraph(vehicle_label, styles["subtitle"]))

    # Вердикт
    verdict_style = _verdict_style_name(report.verdict.value)
    recommendation_ru = _RECOMMENDATION_RU.get(
        report.final_recommendation.value, report.final_recommendation.value
    )
    story.append(
        Paragraph(
            f"{report.verdict_label}  |  {recommendation_ru}",
            styles[verdict_style],
        )
    )
    story.append(Spacer(1, 4))
    story.append(Paragraph(report.summary, styles["body"]))
    story.append(_sep(styles))

    # ------------------------------------------------------------------ #
    # 2. Риски
    # ------------------------------------------------------------------ #
    if report.risks:
        story.append(_section_header("Риски", styles))

        _ensure_fonts()
        font = "DejaVuSans" if _FONT_REGISTERED else "Helvetica"
        font_bold = "DejaVuSans-Bold" if _FONT_REGISTERED else "Helvetica-Bold"

        table_data = [["Риск", "Серьёзность", "Описание", "Стоимость ремонта"]]
        for risk in report.risks[:15]:
            sev = risk.severity.value if hasattr(risk.severity, "value") else str(risk.severity)
            sev_ru = {"high": "Высокая", "medium": "Средняя", "low": "Низкая"}.get(sev, sev)
            cost = ""
            if risk.estimated_cost_min is not None and risk.estimated_cost_max is not None:
                cost = f"{_fmt_rub(risk.estimated_cost_min)}–{_fmt_rub(risk.estimated_cost_max)}"
            else:
                cost = "—"
            table_data.append([
                Paragraph(risk.title, ParagraphStyle("tc", fontName=font, fontSize=8, leading=11)),
                Paragraph(sev_ru, ParagraphStyle("tc", fontName=font, fontSize=8, leading=11)),
                Paragraph(risk.description[:200], ParagraphStyle("tc", fontName=font, fontSize=8, leading=11)),
                Paragraph(cost, ParagraphStyle("tc", fontName=font, fontSize=8, leading=11)),
            ])

        risks_table = Table(
            table_data,
            colWidths=[3.8 * cm, 2.5 * cm, 7.5 * cm, 3.2 * cm],
            repeatRows=1,
        )

        # Цветовая маркировка строк по severity
        risk_style_cmds = [
            ("BACKGROUND", (0, 0), (-1, 0), colors.HexColor("#2c3e50")),
            ("TEXTCOLOR", (0, 0), (-1, 0), colors.white),
            ("FONTNAME", (0, 0), (-1, 0), font_bold),
            ("FONTSIZE", (0, 0), (-1, 0), 9),
            ("ROWBACKGROUNDS", (0, 1), (-1, -1), [colors.HexColor("#f8f9fa"), colors.white]),
            ("GRID", (0, 0), (-1, -1), 0.25, colors.HexColor("#bdc3c7")),
            ("VALIGN", (0, 0), (-1, -1), "TOP"),
            ("TOPPADDING", (0, 0), (-1, -1), 3),
            ("BOTTOMPADDING", (0, 0), (-1, -1), 3),
            ("LEFTPADDING", (0, 0), (-1, -1), 4),
            ("RIGHTPADDING", (0, 0), (-1, -1), 4),
        ]
        for i, risk in enumerate(report.risks[:15], start=1):
            sev = risk.severity.value if hasattr(risk.severity, "value") else str(risk.severity)
            sev_color = _SEVERITY_COLORS.get(sev)
            if sev_color:
                risk_style_cmds.append(("TEXTCOLOR", (1, i), (1, i), sev_color))
                risk_style_cmds.append(("FONTNAME", (1, i), (1, i), font_bold))

        risks_table.setStyle(TableStyle(risk_style_cmds))
        story.append(risks_table)
        story.append(_sep(styles))

    # ------------------------------------------------------------------ #
    # 3. Чеклист осмотра
    # ------------------------------------------------------------------ #
    if report.checklist:
        story.append(_section_header("Чеклист осмотра", styles))
        for item in report.checklist[:12]:
            story.append(
                Paragraph(
                    f"<b>{item.zone} — {item.title}</b>",
                    styles["body"],
                )
            )
            story.append(
                Paragraph(f"Как проверить: {item.how_to_check}", styles["small"])
            )
            if item.red_flags:
                story.append(
                    Paragraph(
                        "Тревожные признаки: " + "; ".join(item.red_flags[:3]),
                        styles["small"],
                    )
                )
            story.append(Spacer(1, 3))
        story.append(_sep(styles))

    # ------------------------------------------------------------------ #
    # 4. Ремонтный бюджет
    # ------------------------------------------------------------------ #
    story.append(_section_header("Ремонтный бюджет", styles))
    story.append(
        Paragraph(
            f"Ориентировочный диапазон: "
            f"<b>{_fmt_rub(report.repair_total_min)} — {_fmt_rub(report.repair_total_max)}</b>",
            styles["body"],
        )
    )

    if report.repair_lines:
        rl_data = [["Категория", "Описание", "Мин.", "Макс."]]
        font = "DejaVuSans" if _FONT_REGISTERED else "Helvetica"
        font_bold = "DejaVuSans-Bold" if _FONT_REGISTERED else "Helvetica-Bold"
        for line in report.repair_lines[:10]:
            rl_data.append([
                Paragraph(line.category, ParagraphStyle("tc", fontName=font, fontSize=8, leading=11)),
                Paragraph(line.description[:150], ParagraphStyle("tc", fontName=font, fontSize=8, leading=11)),
                Paragraph(_fmt_rub(line.min_rub), ParagraphStyle("tc", fontName=font, fontSize=8, leading=11)),
                Paragraph(_fmt_rub(line.max_rub), ParagraphStyle("tc", fontName=font, fontSize=8, leading=11)),
            ])
        rl_table = Table(
            rl_data,
            colWidths=[3.5 * cm, 9 * cm, 2.5 * cm, 2 * cm],
            repeatRows=1,
        )
        rl_table.setStyle(TableStyle([
            ("BACKGROUND", (0, 0), (-1, 0), colors.HexColor("#2c3e50")),
            ("TEXTCOLOR", (0, 0), (-1, 0), colors.white),
            ("FONTNAME", (0, 0), (-1, 0), font_bold),
            ("FONTSIZE", (0, 0), (-1, 0), 9),
            ("ROWBACKGROUNDS", (0, 1), (-1, -1), [colors.HexColor("#f8f9fa"), colors.white]),
            ("GRID", (0, 0), (-1, -1), 0.25, colors.HexColor("#bdc3c7")),
            ("VALIGN", (0, 0), (-1, -1), "TOP"),
            ("TOPPADDING", (0, 0), (-1, -1), 3),
            ("BOTTOMPADDING", (0, 0), (-1, -1), 3),
            ("LEFTPADDING", (0, 0), (-1, -1), 4),
            ("RIGHTPADDING", (0, 0), (-1, -1), 4),
        ]))
        story.append(rl_table)
    story.append(_sep(styles))

    # ------------------------------------------------------------------ #
    # 5. Торговые аргументы
    # ------------------------------------------------------------------ #
    if report.negotiation_tips:
        story.append(_section_header("Аргументы для торга", styles))
        for tip in report.negotiation_tips:
            story.append(Paragraph(f"• {tip}", styles["body"]))
        story.append(_sep(styles))

    # ------------------------------------------------------------------ #
    # 6. Сравнение с рынком
    # ------------------------------------------------------------------ #
    if report.market_comparison:
        mc = report.market_comparison
        story.append(_section_header("Сравнение с рынком", styles))

        verdict_ru = {
            "above_market": "Дороже рынка",
            "below_market": "Выгоднее рынка",
            "fair_price": "Рыночная цена",
        }.get(mc.verdict, mc.verdict)

        story.append(
            Paragraph(
                f"Вердикт: <b>{verdict_ru}</b>  "
                f"(отклонение {mc.delta_pct:+.1f}%,  "
                f"медиана рынка: {_fmt_rub(mc.median_price)},  "
                f"выборка: {mc.sample_count} объявл.)",
                styles["body"],
            )
        )
        story.append(Paragraph(mc.comment, styles["body"]))
        if mc.search_url:
            story.append(
                Paragraph(
                    f"Поиск на Avito: {mc.search_url}",
                    styles["small"],
                )
            )
        story.append(_sep(styles))

    # ------------------------------------------------------------------ #
    # Нижний колонтитул
    # ------------------------------------------------------------------ #
    story.append(Spacer(1, 6))
    story.append(
        Paragraph(
            "Отчёт сформирован AutoRewier. Данные носят ориентировочный характер — "
            "окончательное решение принимается покупателем на основании личного осмотра.",
            styles["small"],
        )
    )

    doc.build(story)
    return buf.getvalue()

"""Логика вердикта: ТО важнее пробега, описание без дефектов не раздувает ремонт."""

from app.schemas import VehicleInput
from app.services.analysis import build_analysis_report


def test_good_car_with_maintenance_not_skip():
    vehicle = VehicleInput(
        brand="Toyota",
        model="Camry",
        year=2015,
        mileage_km=180_000,
        price_rub=1_200_000,
        description=(
            "Регулярное ТО у дилера. Меняли масло, фильтры, колодки, "
            "сайлентблоки, свечи. Один владелец."
        ),
    )
    report = build_analysis_report(
        vehicle,
        defects=None,
        listing_repairs=[
            "меняли масло и фильтры",
            "новые колодки",
            "сайлентблоки передней подвески",
        ],
    )
    assert report.verdict.value != "skip"
    assert report.repair_total_max < 200_000


def test_mileage_ok_for_year_low_risk():
    vehicle = VehicleInput(brand="Kia", model="Rio", year=2018, mileage_km=120_000)
    report = build_analysis_report(vehicle)
    mileage_risks = [r for r in report.risks if "Пробег" in r.title]
    assert mileage_risks
    assert all(r.severity in ("low", "medium") for r in mileage_risks)


def test_defects_can_trigger_caution():
    vehicle = VehicleInput(
        brand="BMW",
        model="X5",
        year=2010,
        mileage_km=200_000,
        price_rub=1_800_000,
    )
    report = build_analysis_report(
        vehicle,
        defects="стук в подвеске, течь масла, ржавчина на пороге",
    )
    assert report.repair_total_max > 0
    assert report.verdict.value in ("caution", "skip")


def test_final_recommendation_is_present():
    vehicle = VehicleInput(
        brand="Skoda",
        model="Octavia",
        year=2019,
        mileage_km=95_000,
        price_rub=1_450_000,
        description="Один владелец, регулярное ТО, без ДТП.",
    )
    report = build_analysis_report(
        vehicle,
        defects="скол на лобовом стекле",
        listing_repairs=["заменены колодки"],
    )
    assert report.final_recommendation.value in (
        "BUY_WITH_CONFIDENCE",
        "CAUTIOUS",
        "REJECT",
    )
    assert 0 <= report.risk_score <= 100


def test_risks_include_precision_fields():
    vehicle = VehicleInput(
        brand="Toyota",
        model="Corolla",
        year=2013,
        mileage_km=170_000,
        price_rub=950_000,
    )
    report = build_analysis_report(
        vehicle,
        defects="течь масла и гул ступичного подшипника",
    )
    assert report.risks
    for risk in report.risks:
        assert risk.evidence
        assert risk.rationale
        assert risk.confidence is not None
        assert risk.priority in ("low", "medium", "high")

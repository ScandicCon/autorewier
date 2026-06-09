import asyncio
from pathlib import Path

import pytest
from fastapi.testclient import TestClient
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine

from app.main import app
from app.api.web_routes import _split_fallback_text
from app.schemas import AvitoPartOffer, PartPriceBlock, VehicleInput
from app.services.parsers.base import ParsedListing


@pytest.fixture()
def api_client(tmp_path: Path, monkeypatch: pytest.MonkeyPatch):
    import app.database as database
    import app.services.inspections as inspections
    from app.config import settings

    db_file = tmp_path / "e2e_vehicle_analysis.db"
    test_db_url = f"sqlite+aiosqlite:///{db_file}"
    test_engine = create_async_engine(test_db_url, echo=False)
    test_sessionmaker = async_sessionmaker(
        test_engine, class_=AsyncSession, expire_on_commit=False
    )

    monkeypatch.setattr(settings, "database_url", test_db_url)
    monkeypatch.setattr(database, "engine", test_engine)
    monkeypatch.setattr(database, "async_session", test_sessionmaker)

    async def _no_external_enrichment(report, vehicle, defects, user_preferences, listing_repairs):
        return report

    monkeypatch.setattr(inspections, "_enrich_report", _no_external_enrichment)

    with TestClient(app) as client:
        yield client

    asyncio.run(test_engine.dispose())


def _auth_headers() -> dict[str, str]:
    return {"X-Telegram-Id": "900001"}


def _assert_precise_risk_fields(report: dict) -> None:
    assert report["risks"]
    for risk in report["risks"]:
        assert "evidence" in risk
        assert "rationale" in risk
        assert "confidence" in risk
        assert "priority" in risk
        assert risk["evidence"]
        assert isinstance(risk["evidence"], list)
        assert "source" in risk["evidence"][0]
        assert "signal" in risk["evidence"][0]
        assert risk["rationale"]
        assert risk["confidence"] is not None
        assert risk["priority"] in {"low", "medium", "high"}


def _assert_precise_repair_fields(report: dict) -> None:
    for line in report.get("repair_lines", []):
        assert "evidence" in line
        assert "rationale" in line
        assert "confidence" in line
        assert "priority" in line
        assert line["evidence"]
        assert isinstance(line["evidence"], list)
        assert "source" in line["evidence"][0]
        assert line["priority"] in {"low", "medium", "high"}


def test_vehicle_analysis_manual_flow_with_history(api_client: TestClient):
    create_payload = {
        "vehicle": {
            "brand": "Toyota",
            "model": "Camry",
            "year": 2014,
            "mileage_km": 235000,
            "price_rub": 1300000,
            "description": "Регулярное ТО, но есть стук в подвеске и запотевание двигателя",
        },
        "pre_defects": "стук подвески, течь масла",
        "listing_repairs": "замена масла\nновые тормозные колодки",
        "is_reseller": True,
        "target_resale_price": 1650000,
    }
    create_resp = api_client.post(
        "/api/v1/inspections",
        json=create_payload,
        headers=_auth_headers(),
    )
    assert create_resp.status_code == 200

    created = create_resp.json()
    inspection_id = created["id"]
    assert created["stage"] == "pre_inspection"
    assert created["verdict"] in {"worth_looking", "caution", "skip"}
    assert created["pre_report"]["risks"]
    assert created["pre_report"]["checklist"]
    assert created["pre_report"]["repair_total_max"] > 0
    assert created["pre_report"]["resale"] is not None
    assert created["pre_report"]["resale"]["estimated_margin"] is not None
    _assert_precise_risk_fields(created["pre_report"])
    _assert_precise_repair_fields(created["pre_report"])
    assert created["pre_report"]["analysis_rationale"]
    assert created["pre_report"]["vehicle_passport"]["brand"] == "Toyota"
    assert created["pre_report"]["vehicle_passport"]["source_quality"] in {"partial", "complete"}

    checklist_resp = api_client.get(
        f"/api/v1/inspections/{inspection_id}/checklist",
        headers=_auth_headers(),
    )
    assert checklist_resp.status_code == 200
    checklist = checklist_resp.json()["checklist"]
    assert isinstance(checklist, list)
    assert checklist

    post_payload = {
        "post_defects": "дополнительно: ошибка по коробке передач и гул ступичного подшипника",
        "post_notes": "нужен торг",
    }
    post_resp = api_client.post(
        f"/api/v1/inspections/{inspection_id}/post",
        json=post_payload,
        headers=_auth_headers(),
    )
    assert post_resp.status_code == 200
    post_data = post_resp.json()
    assert post_data["stage"] == "post_inspection"
    assert post_data["post_report"] is not None
    assert post_data["post_report"]["repair_total_max"] > 0
    assert post_data["verdict"] in {"worth_looking", "caution", "skip"}
    _assert_precise_risk_fields(post_data["post_report"])
    _assert_precise_repair_fields(post_data["post_report"])

    by_id_resp = api_client.get(
        f"/api/v1/inspections/{inspection_id}",
        headers=_auth_headers(),
    )
    assert by_id_resp.status_code == 200
    by_id = by_id_resp.json()
    assert by_id["id"] == inspection_id
    assert by_id["stage"] == "post_inspection"

    history_resp = api_client.get("/api/v1/inspections", headers=_auth_headers())
    assert history_resp.status_code == 200
    history = history_resp.json()
    assert any(item["id"] == inspection_id for item in history)


def test_vehicle_analysis_listing_create_flow(api_client: TestClient, monkeypatch: pytest.MonkeyPatch):
    import app.services.inspections as inspections

    async def _fake_parse_listing(url: str) -> ParsedListing:
        return ParsedListing(
            platform="example",
            raw_title="Kia Rio 2018",
            parse_ok=True,
            parse_error=None,
            listing_repairs=["заменены тормозные диски", "новый аккумулятор"],
            vehicle=VehicleInput(
                brand="Kia",
                model="Rio",
                year=2018,
                mileage_km=125000,
                price_rub=980000,
                description="Аккуратная эксплуатация, есть скол на бампере",
            ),
        )

    monkeypatch.setattr(inspections, "parse_listing_url", _fake_parse_listing)
    monkeypatch.setattr(inspections, "is_avito_url", lambda _: False)

    resp = api_client.post(
        "/api/v1/inspections",
        json={"listing_url": "https://example.com/listing/123"},
        headers=_auth_headers(),
    )
    assert resp.status_code == 200

    data = resp.json()
    assert data["stage"] == "pre_inspection"
    assert data["brand"] == "Kia"
    assert data["model"] == "Rio"
    assert data["year"] == 2018
    assert data["pre_report"]["listing_repairs"] == [
        "заменены тормозные диски",
        "новый аккумулятор",
    ]
    assert data["pre_report"]["checklist"]
    assert data["verdict"] in {"worth_looking", "caution", "skip"}
    _assert_precise_risk_fields(data["pre_report"])
    _assert_precise_repair_fields(data["pre_report"])


def test_vehicle_analysis_supports_youla_source(api_client: TestClient, monkeypatch: pytest.MonkeyPatch):
    import app.services.inspections as inspections

    async def _fake_parse_listing(url: str) -> ParsedListing:
        return ParsedListing(
            platform="youla",
            raw_title="Hyundai Solaris 2019",
            parse_ok=True,
            listing_repairs=["замена передних колодок"],
            vehicle=VehicleInput(
                brand="Hyundai",
                model="Solaris",
                year=2019,
                mileage_km=98000,
                price_rub=1010000,
            ),
        )

    monkeypatch.setattr(inspections, "parse_listing_url", _fake_parse_listing)
    monkeypatch.setattr(inspections, "is_avito_url", lambda _: False)
    resp = api_client.post(
        "/api/v1/inspections",
        json={"listing_url": "https://youla.ru/item/123"},
        headers=_auth_headers(),
    )
    assert resp.status_code == 200
    payload = resp.json()
    assert payload["brand"] == "Hyundai"
    assert payload["model"] == "Solaris"


def test_vehicle_analysis_drom_and_generic_listing_flow(
    api_client: TestClient, monkeypatch: pytest.MonkeyPatch
):
    import app.services.inspections as inspections

    async def _fake_parse_listing(url: str) -> ParsedListing:
        if "drom.ru" in url:
            return ParsedListing(
                platform="drom",
                raw_title="Toyota Camry 2014",
                parse_ok=True,
                parse_error=None,
                listing_repairs=["заменены стойки и втулки стабилизатора"],
                vehicle=VehicleInput(
                    brand="Toyota",
                    model="Camry",
                    year=2014,
                    mileage_km=178000,
                    price_rub=1270000,
                ),
            )
        return ParsedListing(
            platform="youla",
            raw_title="Skoda Octavia 2017",
            parse_ok=True,
            parse_error=None,
            listing_repairs=["заменены передние тормозные диски"],
            vehicle=VehicleInput(
                brand="Skoda",
                model="Octavia",
                year=2017,
                mileage_km=141000,
                price_rub=1090000,
            ),
        )

    monkeypatch.setattr(inspections, "parse_listing_url", _fake_parse_listing)
    monkeypatch.setattr(inspections, "is_avito_url", lambda _: False)

    drom_resp = api_client.post(
        "/api/v1/inspections",
        json={
            "listing_url": "https://auto.drom.ru/krasnoyarsk/toyota/camry-123",
            "vehicle": {"year": 2015},
        },
        headers=_auth_headers(),
    )
    assert drom_resp.status_code == 200
    drom_data = drom_resp.json()
    assert drom_data["brand"] == "Toyota"
    assert drom_data["model"] == "Camry"
    assert drom_data["year"] == 2015
    assert drom_data["pre_report"]["listing_repairs"] == [
        "заменены стойки и втулки стабилизатора"
    ]

    generic_resp = api_client.post(
        "/api/v1/inspections",
        json={"listing_url": "https://youla.ru/item/skoda-octavia-42"},
        headers=_auth_headers(),
    )
    assert generic_resp.status_code == 200
    generic_data = generic_resp.json()
    assert generic_data["brand"] == "Skoda"
    assert generic_data["model"] == "Octavia"
    assert generic_data["year"] == 2017
    assert generic_data["pre_report"]["listing_repairs"] == [
        "заменены передние тормозные диски"
    ]


def test_vehicle_analysis_parts_offers_include_replacement_links(
    api_client: TestClient, monkeypatch: pytest.MonkeyPatch
):
    import app.services.inspections as inspections

    async def _enrich_with_deterministic_offers(
        report, vehicle, defects, user_preferences, listing_repairs
    ):
        report.parts_pricing = [
            PartPriceBlock(
                category="Подвеска",
                part_name="Стойка стабилизатора",
                search_query="стойка стабилизатора Toyota Camry 2014",
                search_url="https://www.avito.ru/rossiya/zapchasti_i_aksessuary?q=%D1%81%D1%82%D0%BE%D0%B9%D0%BA%D0%B0+%D1%81%D1%82%D0%B0%D0%B1%D0%B8%D0%BB%D0%B8%D0%B7%D0%B0%D1%82%D0%BE%D1%80%D0%B0+Toyota+Camry+2014",
                avito_offers=[
                    AvitoPartOffer(
                        title="Стойка стабилизатора Toyota Camry",
                        price_rub=3200,
                        url="https://www.avito.ru/moskva/zapchasti_i_aksessuary/stoyka_stabilizatora_1",
                    )
                ],
                avito_min=3200,
                avito_max=3200,
                avito_median=3200,
                estimate_min=3200,
                estimate_max=3200,
                estimate_median=3200,
                links_available=True,
            )
        ]
        return report

    monkeypatch.setattr(inspections, "_enrich_report", _enrich_with_deterministic_offers)

    create_payload = {
        "vehicle": {
            "brand": "Toyota",
            "model": "Camry",
            "year": 2014,
            "mileage_km": 210000,
            "price_rub": 1150000,
        },
        "pre_defects": "подвеска, требуется замена стойки стабилизатора",
    }
    create_resp = api_client.post(
        "/api/v1/inspections",
        json=create_payload,
        headers=_auth_headers(),
    )
    assert create_resp.status_code == 200

    report = create_resp.json()["pre_report"]
    assert report["parts_pricing"]
    block_with_offers = next(
        (block for block in report["parts_pricing"] if block.get("avito_offers")),
        None,
    )
    assert block_with_offers is not None
    for offer in block_with_offers["avito_offers"]:
        assert "url" in offer
        assert offer["url"].startswith("http")
        assert offer["price_rub"] == 3200
    assert block_with_offers["links_available"] is True
    assert block_with_offers["search_url"].startswith("https://")
    assert block_with_offers["estimate_min"] == 3200
    assert block_with_offers["estimate_max"] == 3200
    assert report["replacement_suggestions"]
    suggestion = report["replacement_suggestions"][0]
    assert suggestion["part_name"] == "Стойка стабилизатора"
    assert suggestion["search_url"].startswith("https://")
    assert suggestion["offer_urls"]
    assert suggestion["offer_urls"][0].startswith("http")
    assert suggestion["offer_cards"][0]["url"].startswith("http")
    assert suggestion["price_min_rub"] == 3200
    assert suggestion["price_max_rub"] == 3200
    assert suggestion["marketplace_links"]


def test_vehicle_analysis_with_photo_urls_and_structured_defects(api_client: TestClient):
    payload = {
        "vehicle": {
            "brand": "Mazda",
            "model": "6",
            "year": 2016,
            "price_rub": 1200000,
        },
        "observed_defects": [
            {
                "zone": "body",
                "title": "Сколы на кромке капота",
                "details": "несколько очагов коррозии",
                "linked_photo_indexes": [0],
            }
        ],
        "photos_metadata": [
            {
                "photo_url": " https://example.com/car-front.jpg ",
                "zone": "body",
                "note": "капот крупным планом",
            }
        ],
    }
    resp = api_client.post(
        "/api/v1/inspections",
        json=payload,
        headers=_auth_headers(),
    )
    assert resp.status_code == 200
    data = resp.json()
    assert data["photos_metadata"]
    assert data["photos_metadata"][0]["photo_url"] == "https://example.com/car-front.jpg"
    assert data["observed_defects"][0]["linked_photo_indexes"] == [0]
    assert data["pre_report"]["risks"]


def test_structured_findings_flow_create_and_post(api_client: TestClient):
    create_payload = {
        "vehicle": {
            "brand": "Skoda",
            "model": "Octavia",
            "year": 2017,
            "price_rub": 1090000,
        },
        "pre_defects": "fallback pre text",
        "observed_defects": [
            {
                "zone": "body",
                "title": "Скол крыла",
                "details": "на переднем левом крыле",
                "severity": "low",
                "linked_photo_indexes": [0],
            }
        ],
        "photos_metadata": [
            {
                "photo_url": "https://example.com/photo-1.jpg",
                "zone": "body",
                "note": "скол хорошо виден",
            }
        ],
    }
    create_resp = api_client.post(
        "/api/v1/inspections",
        json=create_payload,
        headers=_auth_headers(),
    )
    assert create_resp.status_code == 200
    created = create_resp.json()
    inspection_id = created["id"]
    assert created["observed_defects"]
    assert created["observed_defects"][0]["title"] == "Скол крыла"
    assert created["photos_metadata"]
    assert created["photos_metadata"][0]["photo_url"] == "https://example.com/photo-1.jpg"
    assert "image_findings" in created["pre_report"]
    assert created["pre_report"]["vehicle_passport"]["source_platform"] is None

    post_payload = {
        "post_defects": "fallback post text",
        "post_notes": "продавец готов уступить",
        "observed_defects": [
            {
                "zone": "transmission",
                "title": "Рывки АКПП",
                "details": "при переключении 2->3",
                "severity": "high",
                "estimated_cost_max": 120000,
                "linked_photo_indexes": [],
            }
        ],
        "photos_metadata": [
            {
                "photo_url": "https://example.com/photo-2.jpg",
                "zone": "transmission",
                "note": "панель с ошибкой",
            }
        ],
    }
    post_resp = api_client.post(
        f"/api/v1/inspections/{inspection_id}/post",
        json=post_payload,
        headers=_auth_headers(),
    )
    assert post_resp.status_code == 200
    post_data = post_resp.json()
    assert post_data["stage"] == "post_inspection"
    assert post_data["observed_defects"][0]["title"] == "Рывки АКПП"
    assert post_data["photos_metadata"][0]["photo_url"] == "https://example.com/photo-2.jpg"


def test_structured_findings_rejects_out_of_range_photo_index(api_client: TestClient):
    payload = {
        "vehicle": {"brand": "Skoda", "model": "Rapid", "year": 2018},
        "observed_defects": [
            {
                "zone": "body",
                "title": "Скол двери",
                "linked_photo_indexes": [1],
            }
        ],
        "photos_metadata": [
            {
                "photo_url": "https://example.com/only-photo.jpg",
                "zone": "body",
            }
        ],
    }
    resp = api_client.post(
        "/api/v1/inspections",
        json=payload,
        headers=_auth_headers(),
    )
    assert resp.status_code == 422
    detail = str(resp.json()["detail"]).lower()
    assert "out-of-range" in detail


def test_structured_findings_rejects_invalid_cost_range(api_client: TestClient):
    payload = {
        "vehicle": {"brand": "Skoda", "model": "Rapid", "year": 2018},
        "observed_defects": [
            {
                "zone": "engine",
                "title": "Течь масла",
                "estimated_cost_min": 50000,
                "estimated_cost_max": 30000,
            }
        ],
    }
    resp = api_client.post(
        "/api/v1/inspections",
        json=payload,
        headers=_auth_headers(),
    )
    assert resp.status_code == 422
    detail = str(resp.json()["detail"]).lower()
    assert "cannot exceed" in detail


def test_listing_parse_invalid_vehicle_payload_maps_to_bad_request(
    api_client: TestClient, monkeypatch: pytest.MonkeyPatch
):
    import app.services.inspections as inspections

    async def _fake_parse_listing_invalid(url: str) -> ParsedListing:
        parsed = ParsedListing(
            platform="example",
            raw_title="Old car invalid payload",
            parse_ok=True,
            parse_error=None,
            listing_repairs=[],
            vehicle=VehicleInput(brand="Kia", model="Rio", year=2018),
        )
        parsed.vehicle = {"brand": "Kia", "model": "Rio", "year": 1970}  # type: ignore[assignment]
        return parsed

    monkeypatch.setattr(inspections, "parse_listing_url", _fake_parse_listing_invalid)
    monkeypatch.setattr(inspections, "is_avito_url", lambda _: False)

    resp = api_client.post(
        "/api/v1/inspections",
        json={"listing_url": "https://example.com/listing/bad"},
        headers=_auth_headers(),
    )
    assert resp.status_code == 400
    assert "Некорректные данные автомобиля" in resp.json()["detail"]


def test_split_fallback_text_strips_marker_for_structured_payload():
    raw = (
        "важный дефект в свободной форме\n\n"
        "--- structured findings ---\n"
        "• Рывки АКПП [high]"
    )
    assert _split_fallback_text(raw, has_structured_payload=True) == "важный дефект в свободной форме"
    assert _split_fallback_text(raw, has_structured_payload=False) == raw.strip()

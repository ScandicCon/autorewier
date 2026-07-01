import { mount } from "@vue/test-utils";
import { describe, expect, it } from "vitest";
import InspectionOverview from "./InspectionOverview.vue";

const inspection = {
  listing_url: "https://www.avito.ru/moskva/avtomobili/toyota_camry_123",
  brand: "Toyota",
  model: "Camry",
  year: 2020,
  mileage_km: 83000,
  price_rub: 2450000,
  vin: "JTNB11HK9K1234567",
  photos_metadata: [
    {
      photo_url: "https://example.com/car-photo-1.jpg",
      zone: "Передний бампер",
      finding: "Следы локального окраса и микротрещина ЛКП",
      confidence: "medium"
    }
  ],
  pre_report: {
    vehicle_passport: {
      brand: "Toyota",
      model: "Camry",
      year: 2020,
      mileage_km: 83000,
      price_rub: 2450000,
      vin: "JTNB11HK9K1234567",
      source_platform: "avito",
      source_listing_url: "https://www.avito.ru/moskva/avtomobili/toyota_camry_123",
      source_quality: "complete"
    },
    risks: [
      {
        title: "Подвеска требует вложений",
        severity: "high",
        description: "Диагностика выявила стук и износ шаровых опор.",
        estimated_cost_min: 18000,
        estimated_cost_max: 42000,
        evidence: [
          { source: "analysis", signal: "inspection", details: "Осмотр выявил люфт в переднем рычаге" },
          { source: "analysis", signal: "road_test", details: "Слышен стук на неровностях" }
        ],
        confidence: 88,
        priority: "high"
      }
    ],
    checklist: [
      {
        zone: "Подвеска",
        title: "Проверить люфт",
        how_to_check: "Поднять авто и проверить люфт рычагов монтажкой."
      }
    ],
    repair_lines: [
      {
        category: "Подвеска",
        description: "Замена шаровых опор",
        min_rub: 12000,
        max_rub: 25000,
        parts_hint: "Опоры + крепеж"
      }
    ],
    parts_pricing: [
      {
        category: "Подвеска",
        part_name: "Шаровая опора",
        search_query: "Шаровая опора Toyota Camry",
        avito_offers: [
          {
            title: "Шаровая опора OEM",
            price_rub: 5400,
            url: "https://example.com/offer/1"
          }
        ]
      }
    ],
    replacement_suggestions: [
      {
        category: "Подвеска",
        part_name: "Шаровая опора",
        source_platforms: ["avito.ru"],
        offer_urls: ["https://example.com/offer/1"],
        price_min_rub: 5400
      }
    ],
    image_findings: [
      {
        source_photo_url: "https://example.com/car-photo-1.jpg",
        zone: "Передний бампер",
        issue: "Следы локального окраса и микротрещина ЛКП",
        confidence: "medium",
        rationale: "Резкий перепад оттенка ЛКП в зоне скола"
      }
    ]
  }
};

describe("InspectionOverview", () => {
  it("renders evidence and replacement links for risks", () => {
    const wrapper = mount(InspectionOverview, {
      props: { inspection }
    });

    const text = wrapper.text();
    expect(text).toContain("Риски сделки");
    expect(text).toContain("Основание");
    expect(text).toContain("P1");
    expect(text).toContain("Высокая уверенность");
    expect(text).toContain("Осмотр выявил люфт в переднем рычаге");
    expect(text).toContain("Запчасти для замены");
    expect(text).toContain("Шаровая опора OEM");
    expect(text).toContain("5\u00A0400 ₽");
    expect(text).toContain("Avito");

    const link = wrapper.get('a[href="https://example.com/offer/1"]');
    expect(link.exists()).toBe(true);
  });
});

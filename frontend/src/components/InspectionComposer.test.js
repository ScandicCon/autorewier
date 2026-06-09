import { mount } from "@vue/test-utils";
import { describe, expect, it } from "vitest";
import InspectionComposer from "./InspectionComposer.vue";

describe("InspectionComposer", () => {
  it("emits generic listing payload with normalized photo URLs", async () => {
    const wrapper = mount(InspectionComposer);

    await wrapper
      .get('input[placeholder*="https://www.avito.ru"]')
      .setValue("https://auto.drom.ru/krasnoyarsk/toyota/camry-123");
    await wrapper.get('select').setValue("generic");
    await wrapper
      .get('textarea[placeholder*="https://site.ru/car-1.jpg"]')
      .setValue(
        "https://img.example.com/car-1.jpg\ninvalid-photo\nhttps://img.example.com/car-1.jpg\nhttps://img.example.com/car-2.jpg"
      );
    await wrapper.get('input[placeholder*="особое внимание"]').setValue("сколы и зазоры");

    await wrapper.get("form").trigger("submit.prevent");

    const [[payload]] = wrapper.emitted("submit");
    expect(payload.listing_url).toBe("https://auto.drom.ru/krasnoyarsk/toyota/camry-123");
    expect(payload.require_avito_parse).toBe(false);
    expect(payload.photos_metadata).toEqual([
      {
        photo_url: "https://img.example.com/car-1.jpg",
        zone: null,
        note: "сколы и зазоры · фото 1"
      },
      {
        photo_url: "https://img.example.com/car-2.jpg",
        zone: null,
        note: "сколы и зазоры · фото 2"
      }
    ]);
  });

  it("auto-detects avito source and enables strict parse", async () => {
    const wrapper = mount(InspectionComposer);
    await wrapper
      .get('input[placeholder*="https://www.avito.ru"]')
      .setValue("https://www.avito.ru/moskva/avtomobili/honda_accord_123");
    await wrapper.get("select").setValue("auto");

    await wrapper.get("form").trigger("submit.prevent");

    const [[payload]] = wrapper.emitted("submit");
    expect(payload.listing_url).toBe("https://www.avito.ru/moskva/avtomobili/honda_accord_123");
    expect(payload.require_avito_parse).toBe(true);
  });
});

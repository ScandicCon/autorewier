(() => {
  const MARKER_START = "--- structured findings ---";

  const listByType = (type, root = document) =>
    Array.from(root.querySelectorAll(`[data-finding-list="${type}"]`));

  const targetsByType = (type, root = document) =>
    Array.from(root.querySelectorAll(`[data-aggregate-target="${type}"]`));

  const getFindingText = (container) => {
    const rows = Array.from(container.querySelectorAll(".finding-item"));
    const lines = [];
    for (const row of rows) {
      const title = row.querySelector('[data-field="title"]')?.value.trim();
      const severity = row.querySelector('[data-field="severity"]')?.value.trim();
      const photos = row.querySelector('[data-field="photos"]')?.value.trim();
      const notes = row.querySelector('[data-field="notes"]')?.value.trim();
      if (!title && !severity && !photos && !notes) {
        continue;
      }
      lines.push(`• ${title || "Без названия"}${severity ? ` [${severity}]` : ""}`);
      if (photos) {
        lines.push(`  Фото: ${photos}`);
      }
      if (notes) {
        lines.push(`  Комментарий: ${notes}`);
      }
    }
    return lines.join("\n");
  };

  const splitPhotoLinks = (raw) =>
    raw
      .split(",")
      .map((part) => part.trim())
      .filter(Boolean);

  const collectStructuredPayload = (type, root = document) => {
    const lists = listByType(type, root);
    const observedDefects = [];
    const photosMetadata = [];
    const zone = type === "pre" ? "pre_inspection" : "post_inspection";

    for (const list of lists) {
      const rows = Array.from(list.querySelectorAll(".finding-item"));
      for (const row of rows) {
        const title = row.querySelector('[data-field="title"]')?.value.trim();
        const severity = row.querySelector('[data-field="severity"]')?.value.trim();
        const photosRaw = row.querySelector('[data-field="photos"]')?.value.trim();
        const notes = row.querySelector('[data-field="notes"]')?.value.trim();
        if (!title && !severity && !photosRaw && !notes) {
          continue;
        }

        const photoIndexes = [];
        for (const photoUrl of splitPhotoLinks(photosRaw || "")) {
          photoIndexes.push(photosMetadata.length);
          photosMetadata.push({
            photo_url: photoUrl,
            zone,
            note: notes || null,
          });
        }

        observedDefects.push({
          zone,
          title: title || "Без названия",
          details: notes || null,
          severity: severity || "medium",
          linked_photo_indexes: photoIndexes,
        });
      }
    }

    return { observedDefects, photosMetadata };
  };

  const mergeStructuredText = (target, structuredText) => {
    const base = (target.value || "").split(MARKER_START)[0].trim();
    if (!structuredText) {
      target.value = base;
      return;
    }
    target.value = `${base}${base ? "\n\n" : ""}${MARKER_START}\n${structuredText}`.trim();
  };

  const updateTargetForType = (type) => {
    const lists = listByType(type);
    const targets = targetsByType(type);
    if (!targets.length || !lists.length) {
      return;
    }
    const collected = lists.map(getFindingText).filter(Boolean).join("\n");
    for (const target of targets) {
      mergeStructuredText(target, collected);
    }
  };

  const findingTemplate = (type, index) => `
    <article class="finding-item">
      <div class="finding-item-grid">
        <label>Дефект #${index}
          <input type="text" data-field="title" placeholder="скол, рывки АКПП, стук подвески">
        </label>
        <label>Критичность
          <select data-field="severity">
            <option value="">Не выбрано</option>
            <option value="high">Высокая</option>
            <option value="medium">Средняя</option>
            <option value="low">Низкая</option>
          </select>
        </label>
        <label class="full">Ссылки на фото
          <input type="text" data-field="photos" placeholder="https://... , https://...">
        </label>
        <label class="full">Заметка
          <textarea rows="2" data-field="notes" placeholder="что видно по фото, где расположен дефект"></textarea>
        </label>
      </div>
      <div class="finding-item-actions">
        <button type="button" class="btn btn-sm btn-outline" data-remove-finding="${type}">Удалить</button>
      </div>
    </article>
  `;

  const addFinding = (type) => {
    const lists = listByType(type);
    for (const list of lists) {
      const index = list.querySelectorAll(".finding-item").length + 1;
      list.insertAdjacentHTML("beforeend", findingTemplate(type, index));
    }
    updateTargetForType(type);
  };

  const upsertHiddenField = (form, name, value) => {
    let input = form.querySelector(`input[name="${name}"]`);
    if (!input) {
      input = document.createElement("input");
      input.type = "hidden";
      input.name = name;
      form.appendChild(input);
    }
    input.value = value;
  };

  document.addEventListener("click", (event) => {
    const addBtn = event.target.closest("[data-add-finding]");
    if (addBtn) {
      const type = addBtn.getAttribute("data-add-finding");
      if (type) {
        addFinding(type);
      }
      return;
    }

    const removeBtn = event.target.closest("[data-remove-finding]");
    if (removeBtn) {
      const type = removeBtn.getAttribute("data-remove-finding");
      removeBtn.closest(".finding-item")?.remove();
      if (type) {
        updateTargetForType(type);
      }
    }
  });

  document.addEventListener("input", (event) => {
    const wrap = event.target.closest("[data-finding-list]");
    if (!wrap) {
      return;
    }
    const type = wrap.getAttribute("data-finding-list");
    if (type) {
      updateTargetForType(type);
    }
  });

  // === Copy negotiation tip ===
  document.addEventListener("click", (event) => {
    const copyBtn = event.target.closest("[data-copy-tip]");
    if (!copyBtn) return;
    const text = copyBtn.getAttribute("data-copy-tip");
    if (!text) return;
    navigator.clipboard.writeText(text).then(() => {
      copyBtn.textContent = "✓ Скопировано";
      copyBtn.classList.add("copied");
      setTimeout(() => {
        copyBtn.textContent = "Скопировать";
        copyBtn.classList.remove("copied");
      }, 2000);
    }).catch(() => {
      // fallback for non-secure contexts
      const ta = document.createElement("textarea");
      ta.value = text;
      ta.style.position = "fixed";
      ta.style.opacity = "0";
      document.body.appendChild(ta);
      ta.select();
      document.execCommand("copy");
      document.body.removeChild(ta);
      copyBtn.textContent = "✓ Скопировано";
      copyBtn.classList.add("copied");
      setTimeout(() => {
        copyBtn.textContent = "Скопировать";
        copyBtn.classList.remove("copied");
      }, 2000);
    });
  });

  // === PDF download with spinner ===
  document.addEventListener("click", (event) => {
    const pdfBtn = event.target.closest("[data-pdf-download]");
    if (!pdfBtn) return;
    event.preventDefault();
    if (pdfBtn.classList.contains("loading")) return;

    const url = pdfBtn.getAttribute("href") || pdfBtn.getAttribute("data-pdf-download");
    pdfBtn.classList.add("loading");

    const token = document.cookie
      .split("; ")
      .find((c) => c.startsWith("access_token="))
      ?.split("=")[1];

    const headers = {};
    if (token) {
      headers["Authorization"] = "Bearer " + decodeURIComponent(token);
    }

    fetch(url, { headers })
      .then((res) => {
        if (!res.ok) throw new Error("Ошибка загрузки PDF");
        return res.blob();
      })
      .then((blob) => {
        const objectUrl = URL.createObjectURL(blob);
        const a = document.createElement("a");
        a.href = objectUrl;
        const filename = url.split("/").slice(-2, -1)[0] || "inspection";
        a.download = `inspection_${filename}.pdf`;
        document.body.appendChild(a);
        a.click();
        document.body.removeChild(a);
        URL.revokeObjectURL(objectUrl);
      })
      .catch((err) => {
        console.error(err);
        // Fallback: direct navigation
        window.location.href = url;
      })
      .finally(() => {
        pdfBtn.classList.remove("loading");
      });
  });

  document.querySelectorAll("form").forEach((form) => {
    form.addEventListener("submit", () => {
      const observedDefects = [];
      const photosMetadata = [];
      ["pre", "post"].forEach((type) => {
        updateTargetForType(type);
        if (!listByType(type, form).length) {
          return;
        }
        const payload = collectStructuredPayload(type, form);
        observedDefects.push(...payload.observedDefects);
        photosMetadata.push(...payload.photosMetadata);
      });
      upsertHiddenField(form, "observed_defects_json", JSON.stringify(observedDefects));
      upsertHiddenField(form, "photos_metadata_json", JSON.stringify(photosMetadata));
    });
  });
})();

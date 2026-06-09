"""Извлечение полного описания продавца с страницы Avito."""

import html as html_lib
import json
import re
from typing import Any

from bs4 import BeautifulSoup

DESCRIPTION_KEYS = (
    "description",
    "descriptiontext",
    "descriptionhtml",
    "autodescription",
    "sellerdescription",
    "sellertext",
    "about",
    "comment",
    "text",
    "value",
)

DOM_SELECTORS = (
    '[data-marker="item-view/item-description"]',
    '[data-marker="item-view/item-description-text"]',
    '[data-marker="item-description/text"]',
    '[data-marker="item-view/description"]',
    'div[itemprop="description"]',
    '[class*="ItemDescription"]',
    '[class*="item-description"]',
    "#bx_item-description",
)


def _clean_text(text: str) -> str:
    text = html_lib.unescape(text)
    text = re.sub(r"<br\s*/?>", "\n", text, flags=re.I)
    text = re.sub(r"<[^>]+>", " ", text)
    text = text.replace("\\n", "\n").replace("\\t", " ")
    text = re.sub(r"[ \t]+\n", "\n", text)
    text = re.sub(r"\n{3,}", "\n\n", text)
    return text.strip()


def _decode_json_string(raw: str) -> str:
    try:
        return json.loads(f'"{raw}"')
    except json.JSONDecodeError:
        return raw.replace("\\n", "\n").replace('\\"', '"').replace("\\/", "/")


def _score_description(text: str) -> int:
    if not text:
        return 0
    t = text.strip()
    if len(t) < 25:
        return 0
    score = len(t)
    low = t.lower()
    if any(
        w in low
        for w in (
            "продам",
            "продаю",
            "менял",
            "замен",
            "то ",
            "состоян",
            "комплект",
            "владел",
            "пробег",
            "мотор",
            "кузов",
            "салон",
        )
    ):
        score += 200
    if t.count("\n") >= 2:
        score += 50
    return score


def _pick_best(candidates: list[str]) -> str | None:
    best = None
    best_score = 0
    for c in candidates:
        cleaned = _clean_text(c)
        sc = _score_description(cleaned)
        if sc > best_score:
            best_score = sc
            best = cleaned
    return best


def _from_dom(soup: BeautifulSoup) -> list[str]:
    found: list[str] = []
    for sel in DOM_SELECTORS:
        for el in soup.select(sel):
            text = el.get_text("\n", strip=True)
            if text and len(text) > 20:
                found.append(text)
    return found


def _walk_json(obj: Any, depth: int = 0) -> list[str]:
    if depth > 18:
        return []
    results: list[str] = []
    if isinstance(obj, dict):
        for key, val in obj.items():
            k = str(key).lower()
            if k in DESCRIPTION_KEYS and isinstance(val, str) and len(val) > 25:
                results.append(val)
            elif k in ("description", "itemdescription", "autodescription") and isinstance(
                val, dict
            ):
                for subk, subv in val.items():
                    if isinstance(subv, str) and len(subv) > 25:
                        results.append(subv)
            else:
                results.extend(_walk_json(val, depth + 1))
    elif isinstance(obj, list):
        for item in obj[:80]:
            results.extend(_walk_json(item, depth + 1))
    return results


def _from_script_json(html: str) -> list[str]:
    found: list[str] = []
    for m in re.finditer(
        r'<script[^>]*>(.*?)</script>',
        html,
        flags=re.DOTALL | re.IGNORECASE,
    ):
        body = m.group(1)
        if "description" not in body.lower() and "продам" not in body.lower():
            continue
        if len(body) < 100:
            continue
        for pat in (
            r'"description"\s*:\s*"((?:\\.|[^"\\]){30,12000})"',
            r'"descriptionText"\s*:\s*"((?:\\.|[^"\\]){30,12000})"',
            r'"autoDescription"\s*:\s*"((?:\\.|[^"\\]){30,12000})"',
        ):
            for match in re.finditer(pat, body, flags=re.IGNORECASE):
                found.append(_decode_json_string(match.group(1)))
        for blob_pat in (
            r'window\.__preloadedState__\s*=\s*(\{.+?\})\s*;',
            r'window\.__initialData__\s*=\s*(\{.+?\})\s*;',
        ):
            bm = re.search(blob_pat, body, re.DOTALL)
            if not bm:
                continue
            try:
                data = json.loads(bm.group(1))
                found.extend(_walk_json(data))
            except json.JSONDecodeError:
                continue
    return found


def _from_json_ld(soup: BeautifulSoup) -> list[str]:
    found: list[str] = []
    for script in soup.select('script[type="application/ld+json"]'):
        if not script.string:
            continue
        try:
            data = json.loads(script.string)
        except json.JSONDecodeError:
            continue
        items = data if isinstance(data, list) else [data]
        for item in items:
            if isinstance(item, dict):
                desc = item.get("description")
                if isinstance(desc, str):
                    found.append(desc)
    return found


def extract_avito_description(html: str) -> str | None:
    soup = BeautifulSoup(html, "lxml")
    candidates: list[str] = []
    candidates.extend(_from_dom(soup))
    candidates.extend(_from_json_ld(soup))
    candidates.extend(_from_script_json(html))
    return _pick_best(candidates)

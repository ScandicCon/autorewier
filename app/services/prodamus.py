"""Интеграция приёма оплаты через Prodamus (платёжная форма payform.ru).

Зачем Prodamus: работает с самозанятыми и сам формирует чеки НПД (передаёт в
ФНС и клиенту), лоялен к тематикам, где отказали агрегаторы. Подходит как
основной провайдер для «ПОДКАПОТ».

Схема (как у Robokassa в robokassa_routes.py):
- создаём Payment (PENDING), его id используем как order_id;
- редиректим покупателя на ссылку payform с суммой и товаром;
- Prodamus присылает уведомление (webhook) с результатом и подписью;
- проверяем подпись + сумму, активируем Pro/начисляем пакет, отвечаем 200.

Подпись Prodamus (класс Hmac из их SDK): значения приводятся к строке,
массив рекурсивно сортируется по ключам (ksort), сериализуется как
http_build_query, затем hmac-sha256 секретным ключом.

ВАЖНО: алгоритм подписи воспроизведён по документации Prodamus и ОБЯЗАТЕЛЬНО
должен быть сверен в тест-режиме Prodamus до боевого запуска. Если подпись
webhook не сходится — сверить сериализацию с актуальным SDK Prodamus
(https://github.com/Prodamus/payform). Безопасность webhook держится на двух
проверках: подпись + совпадение суммы с суммой нашего Payment.
"""
from __future__ import annotations

import hashlib
import hmac
from urllib.parse import quote_plus, urlencode

from app.config import settings


def is_configured() -> bool:
    return settings.prodamus_enabled


# ---------------------------------------------------------------------------
# Подпись (совместимо с Prodamus\Hmac)
# ---------------------------------------------------------------------------

def _flatten_sorted(data, parent: str = "") -> list[tuple[str, str]]:
    """Рекурсивный ksort + плоские пары ключ->строка в нотации http_build_query.

    dict -> ключи сортируются по возрастанию; list -> сохраняется порядок с
    индексами. Значения приводятся к строке (как array_walk_recursive в PHP).
    """
    out: list[tuple[str, str]] = []
    if isinstance(data, dict):
        for key in sorted(data.keys(), key=lambda x: str(x)):
            path = f"{parent}[{key}]" if parent else str(key)
            out.extend(_flatten_sorted(data[key], path))
    elif isinstance(data, (list, tuple)):
        for index, value in enumerate(data):
            path = f"{parent}[{index}]" if parent else str(index)
            out.extend(_flatten_sorted(value, path))
    else:
        value = "" if data is None else str(data)
        out.append((parent, value))
    return out


def _sign(data: dict, secret: str) -> str:
    pairs = _flatten_sorted(data)
    # http_build_query по умолчанию кодирует по RFC1738 (пробел -> '+').
    query = "&".join(f"{quote_plus(k)}={quote_plus(v)}" for k, v in pairs)
    return hmac.new(secret.encode("utf-8"), query.encode("utf-8"), hashlib.sha256).hexdigest()


def verify_webhook_signature(data: dict, signature: str | None) -> bool:
    """Проверяет подпись входящего уведомления Prodamus в константном времени."""
    if not signature:
        return False
    secret = settings.prodamus_secret_key.strip()
    if not secret:
        return False
    payload = {k: v for k, v in data.items() if k.lower() not in ("signature", "sign")}
    expected = _sign(payload, secret)
    return hmac.compare_digest(expected.lower(), str(signature).lower())


# ---------------------------------------------------------------------------
# Ссылка на оплату
# ---------------------------------------------------------------------------

def build_payment_url(
    *,
    order_id: int | str,
    amount_rub: int,
    description: str,
    customer_email: str | None = None,
) -> str:
    """Собирает ссылку на платёжную форму Prodamus.

    Подпись на исходящую ссылку не кладём намеренно: безопасность обеспечивает
    webhook (подпись Prodamus + сверка суммы с нашим Payment). Даже если
    покупатель изменит сумму в ссылке, webhook с несовпавшей суммой не начислит
    доступ. Это устраняет риск «сломать оплату» из-за неточной исходящей подписи.
    """
    form_url = settings.prodamus_form_url.strip().rstrip("/")
    params: dict[str, str] = {
        "order_id": str(order_id),
        "do": "pay",
        # Товарная позиция нужна Prodamus для корректного чека НПД.
        "products[0][name]": description,
        "products[0][price]": f"{amount_rub}",
        "products[0][quantity]": "1",
        "urlReturn": settings.prodamus_return_url,
        "urlSuccess": settings.prodamus_return_url,
    }
    if customer_email:
        params["customer_email"] = customer_email
    return f"{form_url}/?{urlencode(params)}"


def is_success_payload(data: dict) -> bool:
    """Prodamus сообщает статус оплаты в поле payment_status = 'success'."""
    status = str(data.get("payment_status") or data.get("status") or "").lower()
    return status in ("success", "succeeded", "paid")

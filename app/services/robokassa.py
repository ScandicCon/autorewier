"""Интеграция приёма оплаты через Robokassa.

Схема (подтверждена docs.robokassa.ru):
- Инициация: redirect пользователя на PAYMENT_URL с подписанными параметрами.
  Подпись = MD5("MerchantLogin:OutSum:InvId[:Receipt]:Password1[:Shp_*]").
- Уведомление (ResultURL/webhook): Robokassa присылает OutSum, InvId, SignatureValue
  и наши Shp_*-параметры. Подпись = MD5("OutSum:InvId:Password2[:Shp_*]").
  В ответ магазин обязан вернуть строку "OK{InvId}".

Ключи читаются из окружения (чтобы не трогать app/config.py):
  ROBOKASSA_MERCHANT_LOGIN, ROBOKASSA_PASSWORD1, ROBOKASSA_PASSWORD2, ROBOKASSA_TEST_MODE.

Shp_*-параметры используем, чтобы протащить id пользователя и тип покупки через
платёж — Robokassa вернёт их в webhook без изменений.
"""

import hashlib
import hmac
import json
import os
from urllib.parse import quote, urlencode

PAYMENT_URL = "https://auth.robokassa.ru/Merchant/Index.aspx"


def _env(name: str, default: str = "") -> str:
    return (os.environ.get(name) or default).strip()


def is_configured() -> bool:
    return bool(
        _env("ROBOKASSA_MERCHANT_LOGIN")
        and _env("ROBOKASSA_PASSWORD1")
        and _env("ROBOKASSA_PASSWORD2")
    )


def is_test_mode() -> bool:
    return _env("ROBOKASSA_TEST_MODE", "0").lower() in ("1", "true", "yes", "on")


def _md5(value: str) -> str:
    return hashlib.md5(value.encode("utf-8")).hexdigest()


def _shp_suffix(shp: dict | None) -> str:
    """Shp_*-параметры в подписи: по алфавиту, в формате ':key=value'."""
    if not shp:
        return ""
    return "".join(f":{key}={shp[key]}" for key in sorted(shp))


def _encode_receipt(receipt: dict | None) -> str | None:
    """Минимизированный JSON чека → URL-encode (как требует Robokassa)."""
    if not receipt:
        return None
    compact = json.dumps(receipt, ensure_ascii=False, separators=(",", ":"))
    return quote(compact, safe="")


def build_payment_signature(
    merchant_login: str,
    out_sum: str,
    inv_id: int | str,
    password1: str,
    *,
    receipt_encoded: str | None = None,
    shp: dict | None = None,
) -> str:
    """Подпись для инициации платежа."""
    parts = [merchant_login, out_sum, str(inv_id)]
    if receipt_encoded:
        parts.append(receipt_encoded)
    parts.append(password1)
    return _md5(":".join(parts) + _shp_suffix(shp))


def build_result_signature(
    out_sum: str,
    inv_id: int | str,
    password2: str,
    *,
    shp: dict | None = None,
) -> str:
    """Ожидаемая подпись уведомления ResultURL."""
    return _md5(f"{out_sum}:{inv_id}:{password2}" + _shp_suffix(shp))


def verify_result_signature(
    out_sum: str,
    inv_id: int | str,
    signature: str,
    *,
    shp: dict | None = None,
) -> bool:
    """Проверяет подпись из webhook (Password2 берётся из окружения)."""
    expected = build_result_signature(
        out_sum, inv_id, _env("ROBOKASSA_PASSWORD2"), shp=shp
    )
    # Константное сравнение против timing-атак (security-ревью 2026-07-10, #5).
    return hmac.compare_digest((signature or "").lower(), expected.lower())


def build_payment_url(
    out_sum: str,
    inv_id: int | str,
    description: str,
    *,
    receipt: dict | None = None,
    shp: dict | None = None,
    email: str | None = None,
) -> str:
    """Собирает URL для перенаправления покупателя на оплату Robokassa."""
    merchant_login = _env("ROBOKASSA_MERCHANT_LOGIN")
    password1 = _env("ROBOKASSA_PASSWORD1")
    receipt_encoded = _encode_receipt(receipt)

    signature = build_payment_signature(
        merchant_login,
        out_sum,
        inv_id,
        password1,
        receipt_encoded=receipt_encoded,
        shp=shp,
    )

    pairs = [
        ("MerchantLogin", merchant_login),
        ("OutSum", out_sum),
        ("InvId", str(inv_id)),
        ("Description", description),
        ("SignatureValue", signature),
        ("Culture", "ru"),
    ]
    if email:
        pairs.append(("Email", email))
    if is_test_mode():
        pairs.append(("IsTest", "1"))
    for key in sorted(shp or {}):
        pairs.append((key, str(shp[key])))

    query = urlencode(pairs)
    # Receipt уже percent-encoded — добавляем как есть, без повторного кодирования.
    if receipt_encoded:
        query += "&Receipt=" + receipt_encoded
    return f"{PAYMENT_URL}?{query}"


def success_response(inv_id: int | str) -> str:
    """Тело ответа на ResultURL, которое ждёт Robokassa."""
    return f"OK{inv_id}"

"""Тесты подписи и сборки URL Robokassa.

Подписи детерминированы (MD5), поэтому проверяемы без боевых ключей.
Формулы сверены с примерами из docs.robokassa.ru.
"""

import hashlib

from app.services import robokassa


def _md5(value: str) -> str:
    return hashlib.md5(value.encode("utf-8")).hexdigest()


def test_payment_signature_basic():
    # Пример из доки: md5("demo:990.00:12:password_1")
    sig = robokassa.build_payment_signature("demo", "990.00", 12, "password_1")
    assert sig == _md5("demo:990.00:12:password_1")


def test_payment_signature_with_shp():
    sig = robokassa.build_payment_signature(
        "demo", "990.00", 12, "password_1", shp={"Shp_user": 5}
    )
    assert sig == _md5("demo:990.00:12:password_1:Shp_user=5")


def test_payment_signature_shp_sorted_alphabetically():
    sig = robokassa.build_payment_signature(
        "demo", "10.00", 1, "p", shp={"Shp_z": "1", "Shp_a": "2"}
    )
    assert sig == _md5("demo:10.00:1:p:Shp_a=2:Shp_z=1")


def test_payment_signature_with_receipt_and_shp():
    # Пример из доки (расширенный): receipt идёт перед Password1.
    receipt = "%7B%22items%22%3A%5B%5D%7D"
    sig = robokassa.build_payment_signature(
        "demo", "8.96", 12345, "password_1",
        receipt_encoded=receipt, shp={"Shp_item": "digital"},
    )
    assert sig == _md5(f"demo:8.96:12345:{receipt}:password_1:Shp_item=digital")


def test_result_verify_ok_and_fail(monkeypatch):
    monkeypatch.setenv("ROBOKASSA_PASSWORD2", "p2")
    good = _md5("990.00:12:p2")
    assert robokassa.verify_result_signature("990.00", 12, good) is True
    assert robokassa.verify_result_signature("990.00", 12, good.upper()) is True
    assert robokassa.verify_result_signature("990.00", 12, "deadbeef") is False


def test_result_verify_with_shp(monkeypatch):
    monkeypatch.setenv("ROBOKASSA_PASSWORD2", "p2")
    good = _md5("990.00:12:p2:Shp_user=5")
    assert robokassa.verify_result_signature("990.00", 12, good, shp={"Shp_user": 5}) is True
    # Без shp подпись не сойдётся.
    assert robokassa.verify_result_signature("990.00", 12, good) is False


def test_build_payment_url(monkeypatch):
    monkeypatch.setenv("ROBOKASSA_MERCHANT_LOGIN", "demo")
    monkeypatch.setenv("ROBOKASSA_PASSWORD1", "password_1")
    monkeypatch.setenv("ROBOKASSA_TEST_MODE", "1")
    url = robokassa.build_payment_url("990.00", 12, "Pro подписка", shp={"Shp_user": 5})
    assert url.startswith("https://auth.robokassa.ru/Merchant/Index.aspx?")
    assert "MerchantLogin=demo" in url
    assert "OutSum=990.00" in url
    assert "InvId=12" in url
    assert "IsTest=1" in url
    assert "Shp_user=5" in url
    assert "SignatureValue=" in url


def test_success_response():
    assert robokassa.success_response(12) == "OK12"


def test_is_configured(monkeypatch):
    monkeypatch.delenv("ROBOKASSA_MERCHANT_LOGIN", raising=False)
    monkeypatch.delenv("ROBOKASSA_PASSWORD1", raising=False)
    monkeypatch.delenv("ROBOKASSA_PASSWORD2", raising=False)
    assert robokassa.is_configured() is False
    monkeypatch.setenv("ROBOKASSA_MERCHANT_LOGIN", "demo")
    monkeypatch.setenv("ROBOKASSA_PASSWORD1", "p1")
    monkeypatch.setenv("ROBOKASSA_PASSWORD2", "p2")
    assert robokassa.is_configured() is True

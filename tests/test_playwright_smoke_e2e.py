import os
import re
import socket
import subprocess
import sys
import time
from pathlib import Path

import httpx
import pytest


def _pick_free_port() -> int:
    with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as sock:
        sock.bind(("127.0.0.1", 0))
        return int(sock.getsockname()[1])


def _wait_for_health(base_url: str, timeout_sec: float = 20.0) -> None:
    deadline = time.monotonic() + timeout_sec
    last_error = "no response yet"
    while time.monotonic() < deadline:
        try:
            resp = httpx.get(f"{base_url}/api/v1/health", timeout=0.5)
            if resp.status_code == 200:
                return
            last_error = f"unexpected status {resp.status_code}"
        except Exception as exc:  # pragma: no cover - startup race handling
            last_error = str(exc)
    raise AssertionError(f"API health check did not become ready: {last_error}")


def test_playwright_register_and_dashboard_smoke(tmp_path: Path):
    if os.getenv("RUN_PLAYWRIGHT_E2E") != "1":
        pytest.skip("Set RUN_PLAYWRIGHT_E2E=1 to enable browser smoke checks")

    playwright = pytest.importorskip("playwright.sync_api")
    repo_root = Path(__file__).resolve().parents[1]
    db_file = tmp_path / "playwright_smoke.db"
    port = _pick_free_port()
    base_url = f"http://127.0.0.1:{port}"
    env = os.environ.copy()
    env["DATABASE_URL"] = f"sqlite+aiosqlite:///{db_file}"
    env["OPENROUTER_API_KEY"] = ""
    env["ADMIN_API_TOKEN"] = "smoke-admin-token"
    env["TASK_QUEUE_ENABLED"] = "1"

    server = subprocess.Popen(
        [
            sys.executable,
            "-m",
            "uvicorn",
            "app.main:app",
            "--host",
            "127.0.0.1",
            "--port",
            str(port),
        ],
        cwd=str(repo_root),
        env=env,
        stdout=subprocess.PIPE,
        stderr=subprocess.STDOUT,
        text=True,
    )

    try:
        _wait_for_health(base_url)
        with playwright.sync_playwright() as p:
            try:
                browser = p.chromium.launch(headless=True)
            except playwright.Error as exc:
                pytest.skip(f"Chromium runtime is unavailable: {exc}")

            page = browser.new_page()
            page.goto(f"{base_url}/cabinet/register", wait_until="domcontentloaded")
            playwright.expect(page.get_by_role("heading", name="Регистрация")).to_be_visible()

            email = "smoke-user@example.com"
            page.get_by_label("Email").fill(email)
            page.get_by_label("Пароль").fill("strongpass123")
            page.get_by_role("button", name="Зарегистрироваться").click()

            playwright.expect(page).to_have_url(re.compile(r".*/cabinet$"))
            playwright.expect(page.get_by_role("heading", name="История проверок")).to_be_visible()
            playwright.expect(
                page.get_by_text("Пока нет проверок. Создайте первую по ссылке на объявление.")
            ).to_be_visible()

            page.get_by_role("link", name="Новая проверка").click()
            playwright.expect(page).to_have_url(re.compile(r".*/cabinet/new$"))
            playwright.expect(page.get_by_role("heading", name="Новая проверка автомобиля")).to_be_visible()
            page.get_by_role("link", name="Ручной ввод").click()
            playwright.expect(page).to_have_url(re.compile(r".*/cabinet/new/manual$"))

            page.get_by_label("Марка").fill("Toyota")
            page.get_by_label("Модель").fill("Camry")
            page.get_by_label("Год").fill("2014")
            page.get_by_label("Пробег, км").fill("210000")
            page.get_by_label("Цена, ₽").fill("1250000")
            page.get_by_label("Ваши требования").fill("Нужен ликвидный автомобиль с прозрачной историей")
            page.get_by_label("Сводный текст дефектов").fill("скрип подвески, запотевание двигателя")
            page.get_by_role("button", name="Построить предварительный отчёт").click()

            playwright.expect(page).to_have_url(re.compile(r".*/cabinet/inspection/\d+$"))
            playwright.expect(page.get_by_role("heading", name="Предварительный вывод")).to_be_visible()
            playwright.expect(page.get_by_role("heading", name="Запчасти и ориентиры цен")).to_be_visible()

            page.get_by_role("link", name="Подписка").click()
            playwright.expect(page).to_have_url(re.compile(r".*/cabinet/subscription$"))
            playwright.expect(page.get_by_role("heading", name="Подписка Pro")).to_be_visible()

            admin_headers = {"X-Admin-Token": "smoke-admin-token"}
            admin_health = httpx.get(f"{base_url}/api/v1/admin/health", headers=admin_headers, timeout=3.0)
            assert admin_health.status_code == 200
            assert admin_health.json()["ok"] is True
            assert admin_health.json()["queue_enabled"] is True

            admin_stats = httpx.get(f"{base_url}/api/v1/admin/stats", headers=admin_headers, timeout=3.0)
            assert admin_stats.status_code == 200
            assert admin_stats.json()["users_total"] >= 1
            browser.close()
    finally:
        server.terminate()
        try:
            server.wait(timeout=10)
        except subprocess.TimeoutExpired:  # pragma: no cover - forced cleanup path
            server.kill()
            server.wait(timeout=5)

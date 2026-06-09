import asyncio
import sys

# Playwright/подпроцессы на Windows требуют ProactorEventLoop
if sys.platform == "win32":
    asyncio.set_event_loop_policy(asyncio.WindowsProactorEventLoopPolicy())

from app.main import run_api

if __name__ == "__main__":
    run_api()

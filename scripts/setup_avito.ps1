# Установка браузера для загрузки объявлений Avito
Set-Location $PSScriptRoot\..
.\.venv\Scripts\pip.exe install playwright
.\.venv\Scripts\playwright.exe install chromium

Write-Host "Готово. Перезапустите: python run_api.py"

# ПОДКАПОТ — Деплой готов

## Frontend (Vercel)
1. Import GitHub repo → Vercel
2. Framework: **Vite**
3. Root directory: `frontend/`
4. Build command: `npm run build`
5. Output dir: `dist`
6. Environment variable:
   ```
   VITE_API_URL=https://your-railway-app.railway.app
   VITE_BASE_PATH=/
   ```

## Backend (Railway)
1. New project → Deploy from GitHub
2. Root directory: оставить пустым (Dockerfile в корне)
3. Environment variables (Railway → Variables):

```
DATABASE_URL=postgresql://...   # Railway автоматически добавит при привязке Postgres
WEB_SECRET_KEY=<случайная строка 64 символа>
WEB_BASE_URL=https://your-railway-app.railway.app
WEB_COOKIE_SECURE=true
WEB_COOKIE_SAMESITE=none
WEB_COOKIE_DOMAIN=

OPENROUTER_API_KEY=sk-or-v1-...
OPENROUTER_MODEL=openai/gpt-4o-mini

SMTP_HOST=smtp.resend.com
SMTP_PORT=587
SMTP_USERNAME=resend
SMTP_PASSWORD=re_...          # ← ВАШ API KEY ОТ RESEND.COM
SMTP_SENDER_EMAIL=noreply@ваш-домен.ru
SMTP_SENDER_NAME=ПОДКАПОТ
SMTP_USE_TLS=true

REQUIRE_EMAIL_VERIFICATION=true
ENFORCE_VERIFIED_ACCOUNTS=false
```

## SMTP (Resend.com — бесплатно 100 писем/день)
1. Зарегистрируйтесь на resend.com
2. API Keys → Create API Key
3. Вставьте ключ в SMTP_PASSWORD
4. Если нет своего домена — используйте `onboarding@resend.dev` как SMTP_SENDER_EMAIL

## CORS (важно!)
В `app/main.py` убедитесь что Vercel домен в allow_origins:
```python
allow_origins=["https://your-app.vercel.app", ...]
```

## Миграции БД
На Railway автоматически запускаются при старте (RUN_ALEMBIC_ON_STARTUP=true).

# Deploy on VPS

## 1) Prepare DNS

- Create `A` record for your domain to VPS public IP.
- Wait until DNS resolves (`nslookup your-domain`).

## 2) Prepare server

```bash
sudo apt-get update
sudo apt-get install -y ca-certificates curl git
curl -fsSL https://get.docker.com | sh
sudo usermod -aG docker $USER
```

Re-login to apply docker group.

## 3) Upload project

```bash
git clone <your_repo_url> autorewier
cd autorewier
cp .env.example .env
```

## 4) Fill `.env`

At minimum set:

```env
WEB_SECRET_KEY=<long-random-secret>
APP_DOMAIN=your-domain.com
TELEGRAM_BOT_TOKEN=<token-from-botfather>
ENVIRONMENT=production
ALLOW_DEV_PAYMENT_BYPASS=false
ALLOW_MOCK_SERVICES=false
```

Optional for production quality:

- `OPENROUTER_API_KEY`
- `YOOKASSA_*`
- `AUTOCODE_*`
- SMTP для подтверждения email:
  - `SMTP_HOST`, `SMTP_PORT`, `SMTP_USERNAME`, `SMTP_PASSWORD`
  - `SMTP_SENDER_EMAIL`, `SMTP_SENDER_NAME`, `SMTP_USE_TLS`
- `ENFORCE_VERIFIED_ACCOUNTS=true` (если хотите требовать верификацию до создания проверок)

## 5) Start production stack

```bash
docker compose -f docker-compose.yml -f docker-compose.vps.yml up -d --build
```

## 6) Verify

```bash
docker compose ps
docker compose logs -f caddy
docker compose logs -f api
docker compose logs -f bot
```

Expected:

- `https://your-domain.com` opens web app
- `https://your-domain.com/docs` opens API docs
- bot process starts without token errors

## 7) Update / reload

```bash
git pull
docker compose -f docker-compose.yml -f docker-compose.vps.yml up -d --build --force-recreate
```

## 8) Backend runbook (deploy/rollback)

### Pre-deploy checks

```bash
docker compose logs --tail=200 api
curl -f https://your-domain.com/api/v1/health
```

### Post-deploy checks

```bash
curl -f https://your-domain.com/api/v1/health
curl -f -H "X-Admin-Token: <token>" https://your-domain.com/api/v1/admin/health
```

### Rollback

```bash
git log --oneline -n 5
git checkout <previous_commit_or_tag>
docker compose -f docker-compose.yml -f docker-compose.vps.yml up -d --build --force-recreate
```

### Notes

- Для production используйте `ENVIRONMENT=production`.
- Для PostgreSQL миграции Alembic применяются на старте API.
- Если откатываете код, сверяйте совместимость схемы БД (Alembic `downgrade` при необходимости запускайте вручную).


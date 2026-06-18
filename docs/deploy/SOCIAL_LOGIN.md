# Вход через соцсети (OAuth) — настройка

> Код входа через Яндекс, VK, Google и Telegram уже реализован. Каждый провайдер **включается только при заданных ключах** (без них кнопка просто не показывается). Ниже — что зарегистрировать у провайдера и какие переменные вписать.

---

## Как работает

- Кнопки соцсетей появляются на страницах входа/регистрации автоматически — для тех провайдеров, что настроены.
- Поток: кнопка → провайдер → бэкенд-callback меняет код на профиль → находит/создаёт пользователя → выдаёт наш **JWT** → фронт логинит (та же схема, что у обычного входа, работает и на мобильных).
- Соц-вход создаёт **подтверждённый** аккаунт (email_verified). Если email совпадает с существующим — соц-аккаунт привязывается к нему.

## Общие переменные (Railway → сервис autorewier)

| Переменная | Значение |
|---|---|
| `OAUTH_REDIRECT_BASE` | `https://autorewier-production.up.railway.app` (публичный URL бэкенда — на него провайдеры возвращают код) |
| `OAUTH_SUCCESS_REDIRECT` | `https://autorewier.vercel.app/oauth-callback` (необязательно; по умолчанию = сайт + `/oauth-callback`) |

**Redirect URI**, который нужно прописывать у каждого провайдера, имеет вид:
```
https://autorewier-production.up.railway.app/api/v1/auth/oauth/<provider>/callback
```
(где `<provider>` = `yandex`, `vk` или `google`).

---

## Яндекс ID

1. **oauth.yandex.ru** → «Создать приложение».
2. Платформа — **Веб-сервисы**. Redirect URI:
   `https://autorewier-production.up.railway.app/api/v1/auth/oauth/yandex/callback`
3. Доступы (права): **«Доступ к адресу электронной почты»** (`login:email`) и логин/имя (`login:info`).
4. Возьми **ID** и **пароль** приложения → в Railway:
   ```
   YANDEX_CLIENT_ID = <ID>
   YANDEX_CLIENT_SECRET = <пароль>
   ```

## VK ID

1. **vk.com/apps?act=manage** → «Создать приложение» (тип — сайт/VK ID).
2. Authorized redirect URI:
   `https://autorewier-production.up.railway.app/api/v1/auth/oauth/vk/callback`
3. В настройках включи доступ к **email**.
4. Возьми **app_id** (ID приложения) и **защищённый ключ** → в Railway:
   ```
   VK_CLIENT_ID = <app_id>
   VK_CLIENT_SECRET = <защищённый ключ>
   ```
> VK переводит вход на новый VK ID SDK. Реализован классический OAuth (`oauth.vk.com`). Если VK потребует именно VK ID — напиши, доработаю слой обмена кода (логика поиска/создания пользователя останется та же).

## Google

1. **console.cloud.google.com** → создать проект → **APIs & Services → OAuth consent screen** (заполни базово, External).
2. **Credentials → Create credentials → OAuth client ID → Web application**.
3. Authorized redirect URIs:
   `https://autorewier-production.up.railway.app/api/v1/auth/oauth/google/callback`
4. Возьми **Client ID** и **Client secret** → в Railway:
   ```
   GOOGLE_CLIENT_ID = <client id>
   GOOGLE_CLIENT_SECRET = <client secret>
   ```

## Telegram

1. У тебя уже есть бот и его токен (`TELEGRAM_BOT_TOKEN` в Railway — он же используется для подписи входа).
2. В **@BotFather** → `/setdomain` → выбери бота → укажи домен: `autorewier.vercel.app` (Telegram разрешает виджет логина только для привязанного домена).
3. На **Vercel** (фронт) добавь переменную с **именем бота** (без `@`):
   ```
   VITE_TELEGRAM_BOT = <username_бота>
   ```
   и сделай **Redeploy** фронта (переменные `VITE_*` зашиваются при сборке).

После этого на странице входа появится кнопка-виджет Telegram.

---

## Проверка

После настройки и деплоя:
1. Открой страницу входа — должны появиться кнопки настроенных провайдеров.
2. Нажми «Войти через …» → подтверди у провайдера → должно вернуть в кабинет (`/app`) уже авторизованным.
3. Если что-то не так — ошибки бэкенда теперь видны в **Sentry**.

## Что нужно задеплоить

Код соц-входа уже в проекте — нужно его закоммитить и запушить (команды — в чате). После пуша Railway и Vercel пересоберутся, и провайдеры активируются по мере появления ключей в переменных.

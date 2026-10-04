# Live Telegram smoke

Требуются BOT_TOKEN в локальном `.env`, HTTPS PUBLIC_ORIGIN и настроенный BotFather Mini App URL. Токен не отправлять в чат и не коммитить. Открыть приложение из настоящего Telegram: проверить имя, `/me` и Secure+HttpOnly cookie в сетевой отладке, отсутствие session/initData в storage и логах. Подменённый initData должен дать 401. Повторить iOS/Android/Desktop. Logout должен инвалидировать сессию; истёкшая сессия просит переоткрыть приложение. Origin другого сайта и mutation без CSRF — 403.

Статус 2026-10-04: NOT_RUN — нет token/HTTPS и клиентских устройств. Подписанные локальные fixtures проверяют серверную реализацию, но не заменяют этот smoke.

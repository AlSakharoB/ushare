# S01 — Telegram identity, сессии и ACL

## Вход

Прочитай: 04_AUTH_AND_SECURITY.md, 03_ARCHITECTURE_AND_DATA.md. Порядок зависимостей — `09_ROADMAP.md`.

## Шаги реализации

1. Реализуй users, sessions и миграции; Telegram ID BIGINT, username nullable, upsert по ID.
2. Реализуй серверную проверку initData по текущей Telegram спецификации, freshness и constant-time comparison. Добавь заранее подписанные fixtures, Unicode и дополнительные поля signature.
3. Создай `/auth/telegram`, `/me`, `/auth/logout`, opaque sessions и cookie настройки. CSRF/Origin, exact CORS, auth limits.
4. Создай reusable access policy и authenticated actor, которые позже вызываются и HTTP, и ботом. Не доверяй user_id из mutation body.
5. Подключи frontend Telegram adapter и безопасный dev login, заблокированный в production.
6. Сделай понятный экран входа/ошибки истёкшей сессии; не заставляй пользователя вводить Telegram token.

## Проверка и приёмка

- Изменённый hash/user, stale/future initData, отсутствующий user и duplicate parameters отвергаются.
- Session expiry/logout/CSRF работают; токен не появляется в frontend storage/logs.
- В production dev auth вызывает fail-fast.
- Auth user identity не подменяется HTTP body.
- Есть documented live Telegram smoke; если токена нет, он NOT_RUN, а не PASS.

## Артефакты этапа

Рабочий код/миграции/документация по scope; meaningful tests; `reports/stages/S01_auth.md`; обновлённый `reports/PROGRESS.md`. Для OCR также benchmark artifacts, для UI — безопасные screenshots.

## Завершение

Выполни `08_STAGE_WORKFLOW.md`: проверь diff/секреты, запиши PASS/FAIL/NOT_RUN по каждому критерию, сделай локальный атомарный commit только своих изменений, сообщи SHA и следующий шаг. Не отмечай DONE при незакрытом обязательном критерии. При поручении всего проекта продолжай следующий независимый этап без повторного запроса разрешения.

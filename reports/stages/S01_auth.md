# S01 — Telegram identity и сессии

Дата UTC: 2026-10-04. Статус: DONE. Базовый HEAD: b26ad81.

## Результат

- HMAC initData по [официальной Telegram спецификации](https://core.telegram.org/bots/webapps#validating-data-received-via-the-mini-app): hash исключается, signature включается, ключ WebAppData.
- Users upsert по BIGINT Telegram ID; opaque session digest в PostgreSQL, HttpOnly/SameSite cookie (Secure для HTTPS), срок 12 часов. CSRF и точный Origin для mutations; frontend не хранит bearer token.
- Общий PostgreSQL rate limiter входа, правила creator/accepted для будущих сервисов, dev login только при явных development + local origin настройках; production fail-fast.
- Frontend подключает Telegram adapter и показывает loading/error/confirmed identity.

## Изменения

auth/, db/auth_models.py, api/auth.py/dependencies.py, migration 0001, frontend Auth/Telegram/API adapters и generated types. Подписанный fixture получен независимо через Node crypto и содержит Unicode + signature; тестовый токен фиктивный.

## Проверки

| Команда / сценарий | Результат | Доказательство |
| --- | --- | --- |
| make UV=/tmp/receiptsplit-tools/bin/uv migrate api-types | PASS | exit 0; migration 0001; generated TS |
| make UV=/tmp/receiptsplit-tools/bin/uv check | PASS | exit 0; ruff/format/mypy 18 source files, 13 unit + 3 PostgreSQL integration tests, 1 frontend test, lint/tsc/build |
| Подпись/Unicode/signature, tamper, duplicate, malformed, freshness edges | PASS | tests/test_auth.py, 12 cases |
| DB session expiry/logout/digest, CSRF/Origin, extra identity, signed missing user, rate limit, dev isolation | PASS | tests/integration/test_auth.py, 2 scenarios |
| git diff --check | PASS | exit 0 |
| Live Telegram | NOT_RUN | docs/testing-telegram.md; token/HTTPS/devices отсутствуют |

Первый mypy выявил тип ReturningInsert, исправлен без ослабления strict. Первый pytest выявил collision имён модулей; importlib import mode устраняет конфликт без удаления тестов. Итоговые проверки выше прошли после исправлений.

## Критерии приёмки

| Критерий | Выполнен | Доказательство |
| --- | --- | --- |
| Invalid/stale/future/duplicate initData отвергается | Да | unit + signed missing-user integration |
| Session expiry/logout/CSRF; no frontend token storage | Да | integration + API adapter review |
| Production dev auth fail-fast | Да | Settings validation unit test |
| Body не подменяет identity | Да | extra=forbid + tampered user tests |
| Live smoke documented и статус честный | Да | docs/testing-telegram.md, NOT_RUN |

## Риски и блокировки

Live Telegram gate остаётся открытым, локальная реализация проверена. Object-specific ACL проверяется в S03–S06, когда появятся объекты. Auth freshness 600 с, future tolerance 30 с — политика приложения. Повтор initData в коротком окне возможен, ограничен rate limiter; полного anti-replay не заявляем.

## Решения

Same-origin: cross-origin API requests не нужны; Origin allowlist из одного PUBLIC_ORIGIN. HTTP cookie без Secure допускается только для локальной development работы; production требует HTTPS. Raw Telegram profile/initData/cookie не логируются.

## Коммит

Planned subject: feat(auth): validate Telegram sessions

## Продолжение

S02: pure денежное ядро, deterministic rounding и property tests.

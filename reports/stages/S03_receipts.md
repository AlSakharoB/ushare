# S03 — Ручные чеки и позиции

Дата UTC: 2026-10-04. Статус: DONE. Базовый HEAD: 560176a.

## Результат

- Создатель создаёт ручной чек с atomic owner membership; CRUD позиций, quantity/price discrepancy review, скидка/чаевые и контроль печатного итога.
- Список своих accepted чеков с UUID cursor/status filter; посторонний получает 404, draft участнику не раскрывает позиции/расчёты/полный состав.
- Calculation API с version/revision, receipt lock для mutations и shared lock для согласованных чтений; financial changes сбрасывают подтверждения.
- Idempotent create через PostgreSQL advisory lock, actor+scope+key/body digest; повтор не создаёт дубль, другой body →409.
- Составные FK долей исключают другой чек; ON DELETE CASCADE убирает shares при удалении позиции. Application use cases общие для HTTP и будущего bot.

## Изменения

DB models и frozen migration 0002, contracts.py, services/receipts.py, api/receipts.py, generated TS. PostgreSQL mutation rate limit 120/min на actor; auth отдельно 20/min. Migrations tests используют уникальный schema и rollback всех DDL, не удаляют рабочие таблицы.

## Проверки

| Команда / сценарий | Результат | Доказательство |
| --- | --- | --- |
| .venv/bin/alembic revision --autogenerate ...; upgrade head; check | PASS | exit 0; 0002 applied; no new upgrade operations |
| make UV=/tmp/receiptsplit-tools/bin/uv api-types check | PASS после исправления test harness | unit 36, frontend lint/typecheck/test(1)/build; первая integration ошибка — expired ORM object в тесте FK, исправлена сохранением UUID |
| make ... check-backend test-integration после окончательных правок | PASS | exit 0; strict mypy 25 source files, 36 unit + 7 real PostgreSQL integration tests |
| Empty и previous schema migration | PASS | test_migrations: два независимых PostgreSQL schema, upgrade head с 0 и 0001 |
| CRUD/ACL/version/idempotency/FK/cascade/rollback | PASS | test_receipts.py; invalid percent 10001 возвращает 422 без изменения version |
| Printed total mismatch/review и line discount reason | PASS | test_receipts.py |
| git diff --check | PASS | exit 0 |

## Критерии приёмки

Все критерии S03 выполнены: рабочий CRUD; только authorised list/read; participant cannot mutate; cascade долей; stale 409 и rollback; миграции empty/previous. Historical snapshot предусмотрен отдельной таблицей на S06; текущие правки не должны менять её JSON.

## Риски и блокировки

Нет блокировок S03. После неуспешного тестового запуска в локальной development DB могли остаться только созданные тестом записи; fixtures не попали в git. В ходе работы появился чужой diff .gitignore: он сохранён и исключён из stage commit.

## Решения

Shared read locks держат receipt стабильным до построения response; writers всегда сначала блокируют receipt. Application layer services использует SQLAlchemy transactions, pure monetary domain остаётся независимым. Список UUID cursor сортирует стабильно по UUID; изменение title увеличивает только version. Item PATCH сохраняет полный редактируемый набор полей; receipt PATCH частичный. Idempotency TTL 24 часа, cached receipt также проверяется на ACL/purge deadline.

## Коммит

Planned subject: feat(receipts): add manual receipt workflow

## Продолжение

S04: контакты приложения, request-only и targeted invitations, заявки, approve/revoke и безопасное удаление участников.

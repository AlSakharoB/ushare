# S00 — Основа проекта

## Вход

Прочитай: 00_README.md, 01_PRODUCT.md, 03_ARCHITECTURE_AND_DATA.md, 08_STAGE_WORKFLOW.md. Порядок зависимостей — `09_ROADMAP.md`.

## Шаги реализации

1. Изучи repo/AGENTS, существующие изменения и окружение. Новый проект создавай без перезаписи файлов пользователя. Рабочее имя ReceiptSplit; пользователь может переименовать.
2. Закрепи ADR: стек, состояния, PostgreSQL job queue, private storage, same-origin auth. Укажи версии реально установленных пакетов и причины отклонений.
3. Создай backend/frontend/infra структуру, lock-файлы, конфигурацию из окружения, .env.example и .gitignore; реальный .env только локально.
4. Подними PostgreSQL/API/frontend и health endpoints. Раздели `/health/live` и `/health/ready`; readiness API проверяет DB, OCR имеет отдельный health.
5. Создай Alembic skeleton, общий error envelope, request_id, логирование без payload secrets, базовый transaction wrapper и Clock abstraction.
6. Подготовь Compose dev-профиль и OCR profile, без обязательной GPU; docker volumes persistent. Добавь стандартные Makefile targets из 08_STAGE_WORKFLOW для уже существующих проверок, документируй реальные runner commands; не создавать пустые success-заглушки будущих проверок.
7. CI: ruff, backend typecheck с осмысленным scope, pytest, frontend lint/typecheck/build, PostgreSQL service для integration tests. UI framework smoke, а не ложный тест денег.
8. Согласуй базовый OpenAPI/DTO money/version и генерацию TS types. В README добавь точные команды setup/start/check/migrate/stop.

## Проверка и приёмка

- Чистое окружение запускается по README; healthy API видит PostgreSQL.
- Backend/frontend собираются; formatter/lint/typecheck проходят.
- Миграция empty database выполняется.
- docker compose config валиден, secrets в примерах и git отсутствуют.
- ADR и reports scaffold есть; состояние этапа отражено честно.

## Артефакты этапа

Рабочий код/миграции/документация по scope; meaningful tests; `reports/stages/S00_foundation.md`; обновлённый `reports/PROGRESS.md`. Для OCR также benchmark artifacts, для UI — безопасные screenshots.

## Завершение

Выполни `08_STAGE_WORKFLOW.md`: проверь diff/секреты, запиши PASS/FAIL/NOT_RUN по каждому критерию, сделай локальный атомарный commit только своих изменений, сообщи SHA и следующий шаг. Не отмечай DONE при незакрытом обязательном критерии. При поручении всего проекта продолжай следующий независимый этап без повторного запроса разрешения.

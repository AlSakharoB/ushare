# S00 — Основа проекта

Дата UTC: 2026-10-04. Статус: DONE. Базовый HEAD: отсутствует (новый repo).

## Результат

- PostgreSQL 16.13, API и frontend собираются и запущены локально через Compose.
- Live health работает без БД, ready выполняет SELECT 1; transaction wrapper откатывает DDL при ошибке.
- Python/JS lock-файлы, Alembic, CI, Makefile, OpenAPI → TS, безопасный error envelope и request_id подготовлены.
- Рабочая копия инструкций в docs/instructions; исходный пользовательский комплект сохранён и не включён в commit.
- OCR подготовлен как отдельный opt-in CPU runtime с локальными моделями; readiness при отсутствующих моделях — 503.

## Изменения

backend/, frontend/, infra/, compose.yaml, Makefile, README, .github/workflows/check.yml, docs/adr/0001-foundation.md. User identity git уже задана пользователем; глобальная конфигурация не менялась.

## Проверки

| Команда / сценарий | Результат | Доказательство |
| --- | --- | --- |
| make UV=/tmp/receiptsplit-tools/bin/uv check-backend | PASS | exit 0; ruff, format (15 files), strict mypy (11 source files), pytest: 1 unit |
| make check-frontend | PASS | exit 0; ESLint, tsc, Vitest 1 test, production Vite build |
| .venv/bin/alembic upgrade head | PASS | exit 0; чистая PostgreSQL, revision 0000 |
| make test-integration | PASS | exit 0; 1 PostgreSQL test: ready + DDL rollback |
| Compose up -d --build api/frontend; exec api ... alembic upgrade head | PASS | exit 0; образы собраны, DB/API healthy, frontend доступен |
| make COMPOSE=/usr/local/lib/docker/cli-plugins/docker-compose smoke | PASS | exit 0; реальные HTTP live/ready и HTML frontend |
| Compose config --quiet | PASS | exit 0; включая OCR profile |
| make api-types | PASS | exit 0; generated TS из реального OpenAPI |
| npm audit fix | PASS | exit 0; 0 vulnerabilities после обновления Router/Vite/Vitest/esbuild |
| git diff --check | PASS | exit 0 |
| Live Telegram / OCR model inference | NOT_RUN | S01/S09; нет token и подготовленных локальных моделей |

Начальная попытка DB-тестов внутри sandbox получила OperationalError; повтор с разрешённым доступом к локальному порту прошёл. Начальная HTTP-проверка в sandbox зависла; вне sandbox проходит за 0,49 с. Эти сбои не скрывались изменением поведения приложения. CI workflow создан, remote CI не запускался: push не поручен.

## Критерии приёмки

| Критерий | Выполнен | Доказательство |
| --- | --- | --- |
| Запуск по README; healthy API видит PostgreSQL | Да | Compose smoke, real ready test |
| Сборки/lint/typecheck | Да | make check-backend/check-frontend |
| Миграция empty DB | Да | Alembic 0000 на новой persistent PostgreSQL |
| Compose config; нет secrets | Да | config --quiet; только local example password, BOT_TOKEN пуст; .env ignored |
| ADR, reports, progress | Да | docs/adr/0001-foundation.md, этот отчёт, PROGRESS |

## Риски и блокировки

Нет блокировок S00. Live Telegram token/HTTPS и клиентские устройства потребуются позже; реальные разрешённые чеки нужны для benchmark S09. OCR образ с тяжёлыми зависимостями и inference ещё не проверен, это gate S09. FastAPI/Starlette предупреждают о будущем переходе TestClient на httpx2; тесты работают.

## Решения

Python 3.12.13; uv 0.10.9; FastAPI 0.142.2; SQLAlchemy 2.0.54; Alembic 1.20.0; aiogram 3.31.0; React 19.2.0; Vite 7.3.6; Vitest 4.1.11; Router 7.18.4; TypeScript 5.9.3. Все транзитивные версии и hashes в lock-файлах. OCR optional lock: PaddleOCR 3.7.0, PaddlePaddle 3.3.1; v5 Cyrillic model family сохраняется, окончательная совместимость проверяется на S09. PostgreSQL 16.13, nginx 1.28.2.

## Коммит

Planned subject: chore(project): scaffold services and checks

## Продолжение

S01 — Telegram identity, opaque sessions, CSRF, ACL. Следом S02 — точное денежное ядро.

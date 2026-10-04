# Архитектура, данные и контракты

## Этап A. Выбрать простой обслуживаемый стек

- Backend: Python 3.12, FastAPI, Pydantic 2, SQLAlchemy 2, Alembic, PostgreSQL 16+.
- Bot: aiogram 3; отдельный процесс, общая библиотека доменных сервисов с API. Бот не обращается к Mini App с секретными токенами.
- Mini App: React, TypeScript strict, Vite, TanStack Query, React Router; CSS variables Telegram, небольшая локальная система компонентов. Не нужен Next.js ради SSR.
- Jobs: отдельный Python worker, таблицы jobs/outbox в PostgreSQL, `FOR UPDATE SKIP LOCKED`, lease/heartbeat и retries. Redis/Celery не добавлять до доказанной потребности.
- OCR: изолированный процесс/контейнер Python, PaddleOCR, OpenCV headless; модель загружается один раз. Тяжёлые зависимости не устанавливать в API/bot образ.
- Storage: private локальный volume для MVP за интерфейсом BlobStore; S3-совместимая реализация возможна позже. Фото не в PostgreSQL, не в публичном static.
- Docker Compose, reverse proxy HTTPS, healthchecks, CI. Совместимые версии библиотек и образов фиксировать lock-файлами/тегами; не копировать `latest` в воспроизводимую сборку.

На S00 проверить текущие официальные API выбранных пакетов и записать реальные зафиксированные версии. При существующем проекте сохранить совместимый стек и оформить ADR при отклонении. Не обещать CPU/GPU производительность до измерения.

## Этап B. Структура репозитория

```text
backend/
  src/receiptsplit/
    api/            # routers, DTO, dependency injection
    auth/           # initData, sessions, access policies
    domain/         # money, states, services; без HTTP/aiogram
    db/             # models, repositories, transactions
    bot/            # handlers, rendering, Telegram adapter
    jobs/           # runner, cleanup, outbox, lease
    ocr/            # provider contracts, parser, quality checks
    storage/        # private BlobStore
    config.py
  migrations/
  tests/            # unit, integration, fixtures
frontend/
  src/
    app/            # routing, providers, Telegram adapter
    features/       # receipts, shares, members, settlements, upload
    shared/         # generated API types, components, money display
  tests/
infra/              # Compose, reverse proxy, Dockerfiles
scripts/            # check, benchmark, smoke, restore
samples/ocr/         # обезличенные fixtures и ground truth
reports/stages/
docs/adr/
docs/instructions/  # этот комплект
```

Доменная логика находится в одном месте. HTTP и bot handlers вызывают одинаковые use cases, проверки роли выполняются в них. OCR возвращает кандидаты, не создаёт подтверждённые долги.

## Этап C. Модель БД

| Таблица | Основные поля и ограничения |
| --- | --- |
| users | UUID, telegram_id BIGINT UNIQUE, username nullable, display_name, timestamps |
| receipts | UUID, owner_user_id, title, currency, status, version, financial_revision, discount/tips mode+value, printed_total, closed_at, purge_at |
| receipt_members | UUID, receipt_id, user_id nullable только для pending адресных приглашений, role, status, confirmed_revision; UNIQUE(receipt_id,user_id) для непустого ID |
| receipt_items | UUID, receipt_id, sort_order, name, quantity NUMERIC, unit_price_minor nullable, line_total_minor, origin(manual/ocr), reviewed |
| item_shares | item_id, member_id, receipt_id, share_bp; UNIQUE(item_id,member_id), 1…10000 |
| invitations | receipt_id, token_digest UNIQUE, target_telegram_id nullable, expires_at, revoked_at, usage policy |
| join_requests | receipt_id, user_id, status, invitation_id; запрет двойной активной заявки |
| settlement_snapshots | receipt_id, revision, полный расчёт, created_at, superseded_at |
| payment_reports | receipt_id, member_id, snapshot_id, amount_minor, status, created_at |
| cash_ledger | receipt_id, member_id, signed kind received/refund/correction, amount_minor, actor_id, report_id nullable, reason, created_at |
| receipt_assets | receipt_id, storage_key, bytes, mime, checksum, status |
| ocr_jobs / job_attempts | receipt_id, asset refs, status, model revision, lease, attempts, typed candidate result |
| outbox_events | receipt_id nullable, type, payload minimal, attempts, lease, delivered_at |
| idempotency_keys | actor_id, route scope, key_digest, request_digest, result, receipt_id, expires_at |
| receipt_audit_events | receipt_id, actor_id, event type, revision, minimal diff, created_at |
| asset_delete_jobs | storage_key, retry metadata; без суммы, фото, user/receipt ID после purge |
| purge_tombstones | непрозрачный случайный receipt UUID, expires_at; без участников/позиций/денег |

Привязка owner к accepted member создаётся атомарно. Все денежные значения >=0, кроме явно подписанных компенсирующих ledger операций. Не разрешать комбинации mode/value, не соответствующие схеме.

Составные FK/ограничения должны исключать долю на позицию из другого чека и ledger на участника из другого чека. Проверка общей доли — сервис + блокировка receipt, её нельзя выразить простым CHECK одной строки. `ON DELETE CASCADE` для зависимых данных чека, но storage удаляется отдельной процедурой. Индексы: membership(user_id,status,receipt_id), receipts(status,purge_at), jobs(status,available_at), items(receipt_id,sort_order), ledger(receipt_id,member_id).

## Этап D. API

Namespace `/api/v1`. UUID в пути, но это не защита доступа. В schemas денег minor units, процентов bp; UI форматирует в рубли/проценты. OpenAPI → генерируемые TypeScript-типы.

| Метод / путь | Назначение |
| --- | --- |
| POST /auth/telegram | Проверить initData, выдать серверную сессию |
| POST /auth/logout; GET /me | Завершить сессию; текущая личность |
| GET /receipts | Только собственные и accepted чеки, cursor pagination, фильтр статуса |
| POST /receipts; GET/PATCH /receipts/{id} | Ручное создание, чтение, изменение |
| POST/PATCH/DELETE /receipts/{id}/items[/{item_id}] | CRUD позиций создателем |
| POST /receipts/{id}/assets | Загрузка в private storage |
| POST /receipts/{id}/ocr-jobs; GET …/ocr-jobs/{job_id} | Асинхронное OCR, прогресс и кандидаты |
| POST /receipts/{id}/ocr-jobs/{job_id}/apply | Создатель применяет проверенные кандидаты, expected version |
| GET/POST /receipts/{id}/members | Участники; добавить известного из собственных контактов приложения |
| POST /receipts/{id}/invitations | Адресное или request-only приглашение |
| POST /invitations/resolve; POST /join-requests | Минимальный preview без чека и заявка |
| POST …/join-requests/{request_id}/approve-or-reject | Решение создателя |
| DELETE /receipts/{id}/members/{member_id} | Только допустимое удаление по доменным правилам |
| PUT /receipts/{id}/items/{item_id}/my-share | Абсолютное значение своей доли, не прибавление |
| POST /receipts/{id}/confirm-selection | Подтверждение текущей financial revision |
| GET /receipts/{id}/calculation | Авторитетный расчёт сервера и revision |
| POST …/open; POST …/start-settlement; POST …/return-to-collecting | Переходы состояния |
| POST …/payment-reports | Заявление участника о переводе |
| POST …/payment-reports/{report_id}/review | Создатель подтверждает, отклоняет или отмечает дубликат |
| POST …/cash-ledger | Создатель отмечает приход/возврат/исправление |
| POST /receipts/{id}/close | Проверенное закрытие |

Закрепить точные пути и тела на S00; эти обозначения допускают детализацию, но не потерю сценариев. Mutation финансов получает `expected_version`; критические POST — `Idempotency-Key`. Ошибка: `code`, безопасный `message`, `details`, `request_id`, актуальная version при конфликте. Коды 401/403/404/409/422/429; для постороннего объекта 404. Не раскрывать объект до проверки доступа.

## Этап E. Синхронизация и фоновые задачи

Для MVP polling TanStack Query каждые 3–5 секунд только для открытого видимого чека, немедленный refetch после своей команды и при активации Mini App. После 409 обновить состояние и дать повторить выбор осмысленно; не перезаписывать чужие изменения. SSE возможен позже.

SQL-транзакция финансовой команды: lock receipt → проверить участника/роль/статус/version → изменить данные → пересчитать или snapshot → outbox → commit. Все команды используют одинаковый порядок блокировок. Никаких внешних сетевых вызовов внутри долгой DB-транзакции.

Job delivery at-least-once, обработчики идемпотентны. Unique update_id предотвращает повтор Telegram update. Outbox создаётся в той же транзакции, что изменение; повторные отправки Telegram возможны после сетевого timeout, поэтому сообщения не несут новых денежных действий. OCR completion не применяет кандидаты самостоятельно и не воскрешает удалённый чек.

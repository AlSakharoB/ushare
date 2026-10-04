# 0001 — Основа ReceiptSplit

Дата: 2026-10-04. Статус: принято.

Python 3.12 / FastAPI / SQLAlchemy 2 / PostgreSQL 16; React 19 / TypeScript strict / Vite; aiogram 3 в отдельном процессе. API и бот вызывают общие доменные сервисы. Python зависимости закрепляются uv.lock, JS — package-lock.json; образы имеют конкретные версии.

Деньги — целые копейки, доли — целые bp, округление методом наибольших остатков. Состояния draft → collecting → settling → closed; возврат settling → collecting сохраняет ledger. Создатель подтверждает реальные деньги, закрытие требует точного баланса.

Same-origin opaque cookie + CSRF; Telegram initData проверяется сервером. Private BlobStore на volume, OCR — отдельный runtime, jobs/outbox — PostgreSQL с lease и SKIP LOCKED. Redis и внешние платные провайдеры не нужны. Закрытые данные недоступны ровно через 7 суток UTC.

На хосте Python 3.10, поэтому для разработки скачан CPython 3.12.13 в /tmp, проект имеет собственную .venv. Compose установлен как отдельный CLI plugin; можно передать COMPOSE в make.

Актуальные API проверены по первичным источникам: [FastAPI](https://fastapi.tiangolo.com/tutorial/sql-databases/), [SQLAlchemy transactions](https://docs.sqlalchemy.org/en/20/orm/session_transaction.html), [Vite](https://vite.dev/guide/). Для транзакций используется Session.begin, readiness выполняет настоящий SELECT 1.

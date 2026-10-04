# ReceiptSplit

Telegram-бот и Mini App для распределения общего чека. Язык — русский. Требования: [docs/instructions/00_README.md](docs/instructions/00_README.md). Реализация ведётся по этапам; актуальное состояние — [reports/PROGRESS.md](reports/PROGRESS.md).

## Локальная разработка

Нужны Python 3.12, uv 0.10.9, Node.js 24.15, npm 11, Docker с Compose v2. Скопируйте `.env.example` в `.env`, задайте собственные настройки. Секреты не коммитятся. Без BOT_TOKEN можно запускать автоматические проверки и явный isolated dev login; live Telegram требует token и HTTPS.

```sh
make setup
docker compose up -d db
make migrate
make check
cd backend && uv run uvicorn receiptsplit.api.app:app --port 8000 --no-access-log
# В другом терминале:
cd frontend && npm run dev
```

Mini App: http://localhost:5173, API docs: http://localhost:8000/docs. `/health/live` не зависит от БД; `/health/ready` проверяет PostgreSQL и возвращает 503 при недоступности.

```sh
make start       # сборка, запуск API/DB/frontend и миграция
make smoke      # настоящие HTTP health и frontend
make stop       # остановка без удаления persistent volumes
make api-types  # OpenAPI → TypeScript
```

Compose Mini App: http://localhost:8080, PUBLIC_ORIGIN должен соответствовать этому адресу. Для Telegram требуется внешний HTTPS origin; публикация и настройка BotFather выполняются отдельным поручением.

OCR изолирован в opt-in профиле `docker compose --profile ocr up -d --build`. API не устанавливает тяжёлые OCR dependencies. Модели передаются в read-only volume `ocr-models`; при их отсутствии OCR readiness честно возвращает 503. Подготовка артефактов моделей и benchmark относятся к S09; стандартный запуск не требует GPU или скачивания моделей при первом запросе.

`make check-backend`: ruff/lint/format, strict mypy, unit tests. `make check-frontend`: ESLint, tsc, Vitest, production build. `make test-integration` требует настоящую PostgreSQL и применённые миграции. `make check` включает все эти проверки и не скрывает недоступную БД. OCR benchmark будет отдельной командой с реальным набором обезличенных чеков.

На S06 backend поддерживает полный ручной сценарий: чеки и позиции, приглашения/approval, свои доли, подтверждения выбора, зафиксированные сборы, заявления о переводе, creator receive/refund/correction, правку после денег и закрытие. POST create/start/payment/review/cash/return/close требуют `Idempotency-Key`; финансовые команды — актуальный `expected_version`. Все HTTP mutations проверяют Origin и CSRF. Состав API доступен в `/docs`; суммы — integer minor units, проценты — bp. Интерфейс ручного сценария строится на S07.

Если uv или Compose находятся по другому пути: `make UV=/path/to/uv COMPOSE=/path/to/docker-compose check`. Зафиксированные версии пакетов — в lock-файлах. В исходном `ReceiptSplit_Codex_Instructions/` сохранён пользовательский комплект; рабочие инструкции — в `docs/instructions/`.

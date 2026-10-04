# S08 — Telegram-бот и уведомления

## Вход

Прочитай: 03_ARCHITECTURE_AND_DATA.md, 04_AUTH_AND_SECURITY.md, 06_MINI_APP_UX.md. Порядок зависимостей — `09_ROADMAP.md`.

## Шаги реализации

1. Создай aiogram bot process: /start, /help, /receipts; кнопка открытия Main Mini App/menu. Основной редактирующий интерфейс остаётся Mini App.
2. Start links/mini app startapp передают invite/receipt context; всегда проверять серверную identity/ACL. Подтверждение участия не на основании параметра URL.
3. Фото и document: бот предлагает создать новый draft либо выбрать свой редактируемый чек. Скачивает file_id server-side, проверяет MIME/лимиты и кладёт в private storage. Пока OCR не готов, принять pending job; не утверждать «распознано».
4. Подключи outbox delivery: одобрение участия, начало сборов, уведомление creator о reported transfer, подтверждение/отклонение, изменение финансов, close. Содержание минимальное + кнопка Mini App.
5. Пользователь может открыть Mini App без /start; тогда бот может не иметь права писать. Используй requestWriteAccess при поддержке и по явному действию, fallback показывает уведомления внутри Mini App.
6. Webhook HTTPS/secret header, update dedup; dev long polling отдельно. Graceful shutdown, 429 RetryAfter, transient retry, blocked user permanent failure.
7. Escape названия/имена в Telegram HTML/Markdown. Callback action проверяет actor, receipt status/version; критические деньги подтверждаются в Mini App, не доверять forwarded callback.
8. README BotFather: создать bot, token env, Configure Main Mini App, menu button, public HTTPS URL, webhook secret, проверка /start. Не хранить token в URL логах.

## Проверка и приёмка

- Mocked update/replay/429/blocked scenarios проходят.
- Одна DB business mutation на update даже при повторе webhook.
- Фото/document остаются private и привязаны к owner draft.
- Outbox не отправляет просроченный платёжный CTA после изменения/закрытия/purge.
- Не умеющему получать bot messages пользователю доступен Mini App.
- Live /start/menu/invite smoke проведён при наличии token; иначе NOT_RUN с инструкцией.

## Артефакты этапа

Рабочий код/миграции/документация по scope; meaningful tests; `reports/stages/S08_bot.md`; обновлённый `reports/PROGRESS.md`. Для OCR также benchmark artifacts, для UI — безопасные screenshots.

## Завершение

Выполни `08_STAGE_WORKFLOW.md`: проверь diff/секреты, запиши PASS/FAIL/NOT_RUN по каждому критерию, сделай локальный атомарный commit только своих изменений, сообщи SHA и следующий шаг. Не отмечай DONE при незакрытом обязательном критерии. При поручении всего проекта продолжай следующий независимый этап без повторного запроса разрешения.

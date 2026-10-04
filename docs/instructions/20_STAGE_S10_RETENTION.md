# S10 — Удаление закрытых чеков и восстановление

## Вход

Прочитай: 02_DOMAIN_AND_MONEY.md, 04_AUTH_AND_SECURITY.md, 03_ARCHITECTURE_AND_DATA.md. Порядок зависимостей — `09_ROADMAP.md`.

## Шаги реализации

1. Сервис purge_due_receipts: closed AND purge_at<=server now, UTC. Poll каждые 60 секунд, configurable; при старте catch-up, bounded batches.
2. Сразу с purge_at все read/list/asset endpoints считают чек недоступным. Worker физически удаляет строки при ближайшем успешном запуске, нормальная задержка ≤60 секунд; downtime догоняется. Не обещать миллисекундный hard-delete при выключенном сервере.
3. В транзакции lock receipt → mark inaccessible/удалить sensitive payloads и зависимые rows → durable asset_delete_jobs с opaque key → cascade receipt. Include shares, members, invites, join requests, snapshots, reports, ledger, audit, idempotency results, OCR results/outbox.
4. Storage-delete job удаляет original/crops/preprocessed files/temp; retry при transient failures, ENOENT = success. Без денег/identity в residual deletion task. Никогда не хранить base64 фото в отчётах/logs.
5. Не удалять user profile, которому принадлежат другие чеки. Session/user retention отдельно; требование 7 дней относится к закрытому чеку.
6. Закрытие отменяет pending OCR/долговые уведомления. Purge отменяет все jobs/outbox для чека; worker completion rechecks receipt/expiry и не восстанавливает удалённые rows.
7. Backup политика: MVP по умолчанию без автоматических plaintext backups receipt data. Если включены, явно объявить короткий TTL и границы гарантии; не утверждать, что cascade стирает старые dumps.
8. Restore runbook: восстановить в изоляции, выполнить purge по текущему UTC до включения API/bot/worker, затем проверить assets. Старый snapshot БД не должен снова показывать просроченный чек.
9. Telegram хранит отправленные сообщения и исходные фото вне нашей БД. Их полное стирание не гарантируется; уведомления минимальные. Описать это в privacy screen, а не обещать удаление «отовсюду».

## Проверка и приёмка

- Fake Clock: purge_at−1 sec доступно; ровно purge_at скрыто и eligible; разные часовые пояса не меняют deadline.
- DB cascade удаляет все receipt data, storage удаляет original и derivatives; orphan scan чистый.
- Crash между DB commit и storage delete безопасно догоняется.
- Два workers не ломают purge; delayed OCR completion не воскресит данные.
- Open receipts не удалены; users/другие чеки сохраняются.
- Restore drill скрывает старые expired receipts до opening traffic.
- Физическое удаление на 7 суток+worker interval и external/backups ограничения честно задокументированы.

## Артефакты этапа

Рабочий код/миграции/документация по scope; meaningful tests; `reports/stages/S10_retention.md`; обновлённый `reports/PROGRESS.md`. Для OCR также benchmark artifacts, для UI — безопасные screenshots.

## Завершение

Выполни `08_STAGE_WORKFLOW.md`: проверь diff/секреты, запиши PASS/FAIL/NOT_RUN по каждому критерию, сделай локальный атомарный commit только своих изменений, сообщи SHA и следующий шаг. Не отмечай DONE при незакрытом обязательном критерии. При поручении всего проекта продолжай следующий независимый этап без повторного запроса разрешения.

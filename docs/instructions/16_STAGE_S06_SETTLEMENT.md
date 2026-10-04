# S06 — Сборы, подтверждения и закрытие

## Вход

Прочитай: 02_DOMAIN_AND_MONEY.md, 07_TEST_STRATEGY.md, 03_ARCHITECTURE_AND_DATA.md. Порядок зависимостей — `09_ROADMAP.md`.

## Шаги реализации

1. Миграции snapshot/payment_reports/cash_ledger; snapshot immutable, полный финальный расчёт.
2. Start-settlement: проверка 100% строк, актуальных confirmations, приглашений и review; атомарное фиксирование суммы.
3. Participant report amount для текущего snapshot. Owner review: receive/reject/duplicate; создатель может отметить факт получения без предварительного report.
4. Cash ledger immutable; receipt/refund/correction с причиной, idempotency. Correction не является фактическим возвратом: UI требует выбирать причину и вид записи осмысленно.
5. Return-to-collecting: сохранить ledger и исторический snapshot, supersede pending reports, сброс confirmations; допустимые CRUD уже доступны.
6. Пересчитать balance после повторного snapshot; показывать доплату/переплату, подтверждённый возврат. Не автоматически стирать received при правках.
7. Close: только owner, exact verified balances, unresolved reports нет, snapshot актуален; closed_at/purge_at серверные и immutable.
8. Добавь outbox события сборов/денег/закрытия в той же транзакции; delivery позже подключит bot.

## Проверка и приёмка

- E2E-01 и E2E-04 проходят на API с реальным PostgreSQL.
- Кнопка «Я перевёл» не уменьшает verified balance и не закрывает чек.
- Нулевая доля owner/участника и чек с full discount корректны.
- Закрытие запрещено при недоплате/переплате, unresolved reports, stale revision.
- Partial receipts/refunds корректны; повтор подтверждения не удваивает приход.
- Race close vs edit/confirm не создаёт inconsistent snapshot.
- Повтор close сохраняет исходный purge_at.

## Артефакты этапа

Рабочий код/миграции/документация по scope; meaningful tests; `reports/stages/S06_settlement.md`; обновлённый `reports/PROGRESS.md`. Для OCR также benchmark artifacts, для UI — безопасные screenshots.

## Завершение

Выполни `08_STAGE_WORKFLOW.md`: проверь diff/секреты, запиши PASS/FAIL/NOT_RUN по каждому критерию, сделай локальный атомарный commit только своих изменений, сообщи SHA и следующий шаг. Не отмечай DONE при незакрытом обязательном критерии. При поручении всего проекта продолжай следующий независимый этап без повторного запроса разрешения.

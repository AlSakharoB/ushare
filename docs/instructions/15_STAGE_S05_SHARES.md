# S05 — Доли позиций и конкурентный выбор

## Вход

Прочитай: 02_DOMAIN_AND_MONEY.md, 06_MINI_APP_UX.md, 07_TEST_STRATEGY.md. Порядок зависимостей — `09_ROADMAP.md`.

## Шаги реализации

1. Миграции shares/confirmations; constraints на item/member из того же чека.
2. Реализуй PUT my-share: абсолютные bp, 0=удалить, только свой member. Запретить mutation вне collecting.
3. Под receipt lock проверь version и общий share sum; rollback при overflow. Все писатели финансов используют этот же lock.
4. Calculation показывает shared amounts, unassigned, own/other summary. Создатель выбирает свою часть тем же способом.
5. Реализуй explicit owner take-remaining по одной/всем строкам, с preview и expected version; owner не редактирует чужие доли втайне.
6. Confirm-selection на текущей revision; финансовое изменение сбрасывает confirmations. Polling contract позволяет увидеть актуальную version.
7. Реализуй integration race tests в PostgreSQL с barrier для действительно одновременного старта, а не последовательные вызовы.

## Проверка и приёмка

- 0%, 100%, 12,34% проходят и дают правильные суммы.
- Два пользователя одновременно не получают суммарно >100%.
- Чужую долю нельзя менять ни подменой member_id, ни item_id другого чека.
- Нераспределённый остаток не становится долгом owner автоматически.
- Confirmed revision инвалидируется при финансовой правке.
- 409 содержит безопасные данные для refetch; повтор не дублирует изменение.

## Артефакты этапа

Рабочий код/миграции/документация по scope; meaningful tests; `reports/stages/S05_shares.md`; обновлённый `reports/PROGRESS.md`. Для OCR также benchmark artifacts, для UI — безопасные screenshots.

## Завершение

Выполни `08_STAGE_WORKFLOW.md`: проверь diff/секреты, запиши PASS/FAIL/NOT_RUN по каждому критерию, сделай локальный атомарный commit только своих изменений, сообщи SHA и следующий шаг. Не отмечай DONE при незакрытом обязательном критерии. При поручении всего проекта продолжай следующий независимый этап без повторного запроса разрешения.

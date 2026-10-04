# S02 — Денежное ядро и состояния

## Вход

Прочитай: 02_DOMAIN_AND_MONEY.md, 07_TEST_STRATEGY.md. Порядок зависимостей — `09_ROADMAP.md`.

## Шаги реализации

1. Реализуй pure domain value objects: Money, ShareBasisPoints, Discount, Tips, exact parse/format. Бизнес-ядро не импортирует FastAPI/aiogram/SQLAlchemy.
2. Реализуй largest remainder на целых/рациональных числах со стабильным tie-break. Поддержи virtual unassigned в preview.
3. Реализуй pipeline: line totals → участники → скидка → чаевые → own cost/expected from others.
4. Определи state transitions и их preconditions, revision semantics, snapshot DTO; cash ledger баланс и close validation.
5. Добавь unit и property-based tests: conservation, bounds, детерминированность перестановки входа, суммы скидки/чаевых, full discount.
6. Сделай API-compatible сериализацию minor units/bp и примеры результатов для эталонов из спецификации.

## Проверка и приёмка

- Все числовые эталоны из 02_DOMAIN_AND_MONEY совпадают точно.
- sum(due + unassigned) равна общему итогу для случайных валидных данных.
- Не принимаются share >100%, negative/NaN, discount >subtotal.
- 0% удаляет долю; деньги не считают через float.
- Участник с 0 долей не получает стандартные чаевые; owner не должен платить себе.
- State machine запрещает неправильные переходы, включая закрытие одним report.

## Артефакты этапа

Рабочий код/миграции/документация по scope; meaningful tests; `reports/stages/S02_money.md`; обновлённый `reports/PROGRESS.md`. Для OCR также benchmark artifacts, для UI — безопасные screenshots.

## Завершение

Выполни `08_STAGE_WORKFLOW.md`: проверь diff/секреты, запиши PASS/FAIL/NOT_RUN по каждому критерию, сделай локальный атомарный commit только своих изменений, сообщи SHA и следующий шаг. Не отмечай DONE при незакрытом обязательном критерии. При поручении всего проекта продолжай следующий независимый этап без повторного запроса разрешения.

# S03 — Ручные чеки и позиции

## Вход

Прочитай: 01_PRODUCT.md, 02_DOMAIN_AND_MONEY.md, 03_ARCHITECTURE_AND_DATA.md. Порядок зависимостей — `09_ROADMAP.md`.

## Шаги реализации

1. Миграции receipts/members/items/audit, ограничения, indexes и composite FK основу. Owner membership создаётся с чеком.
2. Реализуй create/read/list-own с cursor pagination, status filters и только authorised membership.
3. Реализуй owner-only CRUD items и receipt discount/tips/title. Валидация quantity/unit/line total, partial fields и no double discount.
4. Встрой финансовое ядро: calculation endpoint и revision после изменений. OCR origin/review flags зарезервированы, manual reviewed=true.
5. Open draft → collecting только после проверки позиций и финансовых параметров. Draft item данные доступны только создателю.
6. Добавь transaction lock/version, idempotent create, безопасные ошибки, generated frontend contracts.

## Проверка и приёмка

- Создатель создаёт полноценный ручной чек, правит/удаляет строки, меняет скидку/чаевые.
- List не содержит чужих чеков; доступ к чужому UUID даёт 404.
- Participant не может менять позиции или creator-only настройки.
- Удаление строки очищает её shares без orphan; snapshot история проектируется отдельно.
- Stale version даёт 409; failed mutation не частично обновляет БД.
- Миграции пустой и предыдущей схемы проходят.

## Артефакты этапа

Рабочий код/миграции/документация по scope; meaningful tests; `reports/stages/S03_receipts.md`; обновлённый `reports/PROGRESS.md`. Для OCR также benchmark artifacts, для UI — безопасные screenshots.

## Завершение

Выполни `08_STAGE_WORKFLOW.md`: проверь diff/секреты, запиши PASS/FAIL/NOT_RUN по каждому критерию, сделай локальный атомарный commit только своих изменений, сообщи SHA и следующий шаг. Не отмечай DONE при незакрытом обязательном критерии. При поручении всего проекта продолжай следующий независимый этап без повторного запроса разрешения.

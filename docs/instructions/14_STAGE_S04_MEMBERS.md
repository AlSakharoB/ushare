# S04 — Участники и приглашения

## Вход

Прочитай: 04_AUTH_AND_SECURITY.md, 01_PRODUCT.md, 03_ARCHITECTURE_AND_DATA.md. Порядок зависимостей — `09_ROADMAP.md`.

## Шаги реализации

1. Реализуй accepted/pending member, join request и invitations schema. Не представляй свободно введённое имя как Telegram account.
2. Создатель добавляет известного Telegram user из собственных контактов приложения; если ID неизвестен, создаёт request-only ссылку.
3. Адресная ссылка проверяет target Telegram ID; общая ссылка → request → owner approval. До принятия нет позиций, фото или полного списка людей.
4. Токен random/digest/TTL/revoke; принять/одобрить повторно без дубликата. Принятие в draft ведёт на экран ожидания открытия.
5. Membership change увеличивает financial revision, сбрасывает confirmations. В settling сначала явное возвращение к collecting; closed неизменяем.
6. Реализуй удаление только допустимых участников; участника с ledger не удалять. Минимальный безопасный invite preview.

## Проверка и приёмка

- Новый человек через ссылку и approval получает доступ только после acceptance.
- Targeted link от чужого account не проходит.
- Expired/revoked invitation не используется; двойное принятие не дублирует.
- Посторонний не видит данные по invitation token.
- Пользователь видит все свои accepted чеки; pending requests показаны отдельно.
- Удаление участника не теряет финансовые данные.

## Артефакты этапа

Рабочий код/миграции/документация по scope; meaningful tests; `reports/stages/S04_members.md`; обновлённый `reports/PROGRESS.md`. Для OCR также benchmark artifacts, для UI — безопасные screenshots.

## Завершение

Выполни `08_STAGE_WORKFLOW.md`: проверь diff/секреты, запиши PASS/FAIL/NOT_RUN по каждому критерию, сделай локальный атомарный commit только своих изменений, сообщи SHA и следующий шаг. Не отмечай DONE при незакрытом обязательном критерии. При поручении всего проекта продолжай следующий независимый этап без повторного запроса разрешения.

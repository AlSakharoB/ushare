# S07 — Полный Mini App для ручного сценария

## Вход

Прочитай: 06_MINI_APP_UX.md, 03_ARCHITECTURE_AND_DATA.md, 07_TEST_STRATEGY.md. Порядок зависимостей — `09_ROADMAP.md`.

## Шаги реализации

1. Telegram adapter/auth boot/routing/theme/safe areas; fake user только в isolated dev.
2. Мои чеки, фильтры, cursor pagination, создание вручную, owner editor, скидка/чаевые и server calculation.
3. Участники, заявки и invite sharing. Пользователь сам отправляет ссылку через Telegram share/open; приложение не обещает авторассылку неизвестным людям.
4. Share cards с точным percent input, slider, quick buttons, remainder, saving states, confirm-selection; polling видимого чека.
5. Settlement UI: frozen sum, payment report, owner receives/refunds/rejections, balances, явное close.
6. Return-to-editing/удаление строки с предупреждениями и сохранением денег; closed read-only со сроком удаления.
7. All error states, conflict refetch, keyboard/back/unsaved confirmation и accessible labels.
8. Playwright разных пользователей и эталоны E2E-01/02/04/05 через рабочий backend. Скриншоты themes/mobile без приватных данных.

## Проверка и приёмка

- Пользователь проходит полный ручной сценарий через UI, без Swagger и ручных правок БД.
- 320 px, iPhone-like и Android-like viewport не обрезают кнопки/суммы; обе темы читаемы.
- Percent field позволяет 0…100% с 2 знаками и видит реальный свободный остаток.
- Правки через другой browser context обновляются polling/refetch.
- Typecheck/build/lint и Playwright проходят.
- Screenshot review выполнен; не выдавать браузерную проверку за live Telegram WebView.

## Артефакты этапа

Рабочий код/миграции/документация по scope; meaningful tests; `reports/stages/S07_mini_app.md`; обновлённый `reports/PROGRESS.md`. Для OCR также benchmark artifacts, для UI — безопасные screenshots.

## Завершение

Выполни `08_STAGE_WORKFLOW.md`: проверь diff/секреты, запиши PASS/FAIL/NOT_RUN по каждому критерию, сделай локальный атомарный commit только своих изменений, сообщи SHA и следующий шаг. Не отмечай DONE при незакрытом обязательном критерии. При поручении всего проекта продолжай следующий независимый этап без повторного запроса разрешения.

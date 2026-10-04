# ReceiptSplit — правила агента

Работай по `docs/instructions/00_README.md` и связанным файлам. Если комплект пока лежит рядом с этим AGENTS.md, сначала перенеси инструкции в `docs/instructions/` аккуратно и обнови ссылки. Существующий root AGENTS.md не перезаписывай: добавь ссылку и согласуй применимые правила.

## Обязательное чтение

`01_PRODUCT.md`, `02_DOMAIN_AND_MONEY.md`, `03_ARCHITECTURE_AND_DATA.md`, `04_AUTH_AND_SECURITY.md`, `08_STAGE_WORKFLOW.md`, `09_ROADMAP.md` и файл текущего этапа. Перед OCR — `05_OCR_STRATEGY.md`; перед UI — `06_MINI_APP_UX.md`; перед приёмкой — `07_TEST_STRATEGY.md`.

## Выполнение

- Следуй S00–S11, dependencies и acceptance criteria. Не заменяй рабочую интеграцию моками.
- Telegram identity проверяется сервером, membership/role на каждом объекте.
- Money integers minor units, проценты bp, deterministic rounding, PostgreSQL transactions.
- Только создатель подтверждает получение и закрытие. Участник сообщает перевод.
- После редактирования деньги не пропадают; пересчёт и переплаты обрабатываются.
- Чек через 7 дней после close недоступен и удаляется worker с assets/children.
- OCR — PaddleOCR Cyrillic baseline, обязательный review, реальный benchmark. Никаких выдуманных метрик.
- После этапа targeted tests, отчёт, PROGRESS, local commit и SHA. PASS/FAIL/NOT_RUN писать честно.
- Пользователь поручил локальные stage commits. Push/deploy/paid integrations — отдельное поручение.
- Не стирай чужие изменения, не коммить secrets/приватные фото/weights, не переписывай чужую историю.
- При поручении всего проекта продолжай самостоятельно. Внешняя блокировка не мешает независимой работе.

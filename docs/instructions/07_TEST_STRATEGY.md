# Проверки и критерии качества

## Этап A. Инструменты

Backend: pytest, Hypothesis, HTTPX/ASGI integration; PostgreSQL test instance для транзакций. Frontend: TypeScript, ESLint, Vitest, Playwright. OCR: CLI benchmark с машинно-читаемым JSON и безопасным Markdown report. CI: lint/typecheck/unit/integration/build, миграции на чистой PostgreSQL; OCR smoke отдельно с заранее доступными pinned weights, полный benchmark по требованию.

Не заменять PostgreSQL SQLite в тестах locking/constraints. Telegram/API внешние ошибки мокируются для детерминированных тестов, но реальные интеграционные smoke отмечаются отдельно. Не писать тесты только ради проверки названий файлов/дословного зеркала реализации.

## Этап B. Матрица

| Область | Обязательные проверки |
| --- | --- |
| Auth | valid/tampered/stale/future initData, Unicode и signature, отсутствие user, replay policy, expiry, CSRF, dev auth в prod |
| ACL | чужой чек/item/asset/job/report, чужая доля, participant редактирует creator-only поля |
| Money | 0/100%, копейки, fractions, total bp, discount bounds, tips bases, full discount, exact conservation, stable tie-break |
| DB | миграции empty и upgrade, composite FK, constraints, каскады, отсутствие orphan assets |
| Manual CRUD | создание, строки, правки, удаление с долями, название, printed total discrepancy |
| Invites | unknown ID request, targeted чужой ID, expiry/revoke, повтор accept, creator approval, no data leak |
| Concurrency | два участника берут последние проценты, close vs edit, confirm vs return-to-editing, purge vs OCR finish |
| Idempotency | create/payment/close/apply повторяется один раз; тот же key другой body →409 |
| Settlement | owner share, zero due, participant report не платёж, partial receipts, overpay/refund, edit preserves cash |
| Bot | update replay, photo/document, caption injection/escaping, callback identity, blocked user, timeout/429 |
| OCR | наклон, изгиб, glare, blur, duplicates, multipage, missing numbers, discount twice, invalid output, real benchmark |
| Purge | exactly 7 days UTC, unrelated users retained, row cascades, assets, retries, offline catch-up, restored backup |
| UX | mobile widths, themes, safe areas, loading/error, 409, key flows, no fake save |

## Этап C. Сквозные эталоны

### E2E-01: обычный ручной чек

Создатель A, участники B и C, посторонний D. A создаёт строки: пицца 1200 ₽, напитки 600 ₽. Скидка 10%, чаевые 10% после скидки. A берёт 50% пиццы; B берёт 50% пиццы и 50% напитков; C берёт 50% напитков. Итог 1782 ₽: A=594 ₽, B=891 ₽, C=297 ₽. Все подтверждают → A начинает сбор. B отмечает перевод → A подтверждает 891 ₽. C отмечает перевод → закрытие ещё запрещено → A подтверждает 297 ₽ → A явно закрывает. D ни в какой момент не получает данные. Через 7 суток нет чека/фото/расчётов у A/B/C.

### E2E-02: частичный выбор и гонка

Строка 1000 ₽. B вводит 60%, C одновременно 60% от одной version. Только один проходит, другой получает 409. На повтор C выбирает 40% при актуальном состоянии. A не может начать сбор при неполных/неподтверждённых долях. Проверить 0% и изменение своей части.

### E2E-03: OCR → проверка → распределение

Настоящий обезличенный русский чек с наклоном. Асинхронное распознавание, показ проблемного поля, ручное исправление и подтверждение. Добавление строк не дублируется повтором apply. Далее сценарий E2E-01 с фактическими суммами fixture. Записать model version и реальное время.

### E2E-04: редактирование после денег

B должен 500 ₽ и A подтвердил получение 500 ₽. A явно возвращает чек к распределению, удаляет/меняет строку так, что B должен 400 ₽. Полученные 500 ₽ остаются. После переподтверждения и нового snapshot закрытие блокируется до подтверждённого возврата 100 ₽. Повторить с новым долгом 600 ₽: требуется доплата 100 ₽.

### E2E-05: приглашение нового пользователя

A не знает ID B, делится общей ссылкой. B получает только безопасный preview, авторизуется, подаёт заявку; повтор не дублирует. A принимает; B видит чек после open. D по той же ссылке без approval не видит данные. Отозванная/истёкшая ссылка не создаёт заявку.

## Этап D. Ворота этапов

После каждого этапа: targeted проверки изменённого поведения + предусмотренные для него integration проверки. S02 — все money properties; S05/S06 — обязательные race tests; S09 — реальные OCR proof; S10 — purge и restore; S11 — полная регрессия, сборка и smoke. Не прогонять тяжёлый OCR suite после изменения только текста кнопки.

Если команда не запускалась — `NOT_RUN` с причиной, а не `PASS`. Нет Telegram token/доступа к устройству/реальных фото → функциональная работа продолжается, но соответствующий gate остаётся BLOCKED. Финальный релиз не считать проверенным, пока обязательные gates не закрыты. Coverage не заменяет сценарии: особенно деньги/ACL/удаление.

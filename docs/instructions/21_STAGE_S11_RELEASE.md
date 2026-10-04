# S11 — Итоговая приёмка и запуск

## Вход

Прочитай: Все спецификации, 07_TEST_STRATEGY.md, 08_STAGE_WORKFLOW.md. Порядок зависимостей — `09_ROADMAP.md`.

## Шаги реализации

1. Проверь R01–R13 и acceptance каждого этапа по фактическим доказательствам. Сведи reports/ACCEPTANCE.md с PASS/FAIL/NOT_RUN и ссылками.
2. Полная backend/frontend регрессия, Hypothesis money, PostgreSQL races, migrations from empty/upgrade, frontend build и E2E-01…05.
3. OCR quality report должен быть актуален production model/config; после смены модели benchmark повторяется. NOT_RUN Qwen допустим, NOT_RUN baseline real dataset — нет.
4. Compose smoke: чистый запуск, persistence после restart, graceful shutdown, readiness, job recovery, cleanup и restore. Проверь production env запрещает dev auth.
5. Проверка live Telegram на доступных iOS/Android/Desktop: auth, menu, invite, photo upload, safe areas/keyboard, theme, close history. Отсутствующие устройства обозначить, не имитировать live доказательство.
6. Security pass: чужие ID/roles, CSRF, rate limits, upload limits, private storage, secrets in bundle/logs, no stale notification.
7. README: пошаговый локальный и production setup, BotFather, HTTPS/reverse proxy, env matrix, миграции, OCR weights/resources, команды check/benchmark/purge/restore, обновление и rollback strategy.
8. Runbook ошибок: token revoked, webhook conflict, model unavailable, disk full, DB outage, job stuck, storage cleanup failures. Метрики минимальные: failed jobs, backlog, expired receipts, asset deletion age, API errors.
9. Подготовь окончательный отчёт: что готово, версии, hardware OCR, ограничения, commit chain, точные команды. Реальную публикацию/регистрацию внешних ресурсов выполняй только по явному поручению.

## Проверка и приёмка

- R01–R13 покрыты, mandatory tests проходят, открытых денежных/ACL/retention проблем нет.
- Полный ручной и сканированный пользовательский сценарий воспроизводим.
- Финальная сборка стартует по README; ничего не зависит от локальных скрытых действий автора.
- OCR baseline прошёл real quality gate; unresolved gates исключают статус «полностью готово».
- Есть понятный runbook/acceptance и итоговый локальный commit.
- Если token/устройство/реальные фото отсутствуют, итог честно BLOCKED/частично проверено с конкретным остатком, а не production-ready.

## Артефакты этапа

Рабочий код/миграции/документация по scope; meaningful tests; `reports/stages/S11_release.md`; обновлённый `reports/PROGRESS.md`. Для OCR также benchmark artifacts, для UI — безопасные screenshots.

## Завершение

Выполни `08_STAGE_WORKFLOW.md`: проверь diff/секреты, запиши PASS/FAIL/NOT_RUN по каждому критерию, сделай локальный атомарный commit только своих изменений, сообщи SHA и следующий шаг. Не отмечай DONE при незакрытом обязательном критерии. При поручении всего проекта продолжай следующий независимый этап без повторного запроса разрешения.

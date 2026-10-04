# S06 — Сборы, реальные деньги и закрытие

Дата UTC: 2026-10-04. Статус: DONE. Базовый HEAD: 1b71f9a.

## Результат

- Start-settlement проверяет все позиции 100% в bp, review, актуальные confirmations, отсутствие pending requests/active unresolved invitations; сохраняет полный immutable snapshot.
- Participant report не меняет cash. Creator review/partial receive/reject/duplicate и direct receive/refund/correction создают неизменяемую ledger. Amount/reason/actor/member проверяются, owner не платит себе.
- Return-to-collecting сохраняет ledger/history, supersedes reported, сбрасывает confirmations; после цены 500→400 появляется refund 100, 500→600 — topup 100.
- Только creator явно закрывает exact balanced receipt без unresolved reports; UTC closed_at/purge_at = +7 суток, replay close не сдвигает дату.
- PostgreSQL защищает UPDATE ledger, snapshot data и closed receipt. Composite FK и current snapshot unique index, atomic outbox, удаление member с денежной историей запрещено.

## Изменения

Migration 0004, settlement_models, application services/API, ReceiptDTO cash/remaining/reports/ledger, generated TS, S04 removal history guard, README. Local Compose пересобран до S06.

## Проверки

| Команда / сценарий | Результат | Доказательство |
| --- | --- | --- |
| Alembic upgrade head/check | PASS | exit 0; 0004, no schema drift |
| pytest tests/integration/test_settlements.py | PASS | exit 0; 5 scenarios за 4,75 с |
| make UV=/tmp/receiptsplit-tools/bin/uv check | PASS | exit 0; strict mypy 33 source files; 36 unit + 14 real PostgreSQL integration; frontend lint/tsc/test(1)/build |
| E2E-01 | PASS | Pizza/drinks, 10%+10%, total1782; A594/B891/C297; reported≠received; duplicate must resolve; explicit close/replay |
| E2E-04 | PASS | Parameterized 400/600 after received500, cash preserved, refund/topup required, historical snapshot500 unchanged |
| Partial receive/correction | PASS | Receive200, compensating correction−100 with reason, remaining400, actual topup400; original immutable |
| Zero due + simultaneous close/return | PASS | Full discount, Barrier(2), responses 200/409, coherent closed/collecting and timestamps |
| DB immutable ledger/snapshot UPDATE | PASS | Both SQL mutations raise DBAPIError; original preserved |
| Empty/previous migrations | PASS | Independent transactional PostgreSQL schemas to 0004 |
| Compose API/frontend rebuild, migration, HTTP smoke | PASS | exit 0; DB/API healthy, live/ready/HTML доступны |
| git diff --check | PASS | exit 0 |

## Критерии приёмки

Все критерии S06 выполнены: E2E-01/E2E-04, report not money, zero/full-discount, under/over/stale/report close blocks, partial/refund/idempotent receive, concurrent close-vs-return, immutable purge date. Ledger/report member guard выполняет денежное ограничение S04.

## Риски и блокировки

Нет блокировок S06. Outbox delivery ещё не включён — S08; это реальные durable события, без утверждения о доставке. Closed receipt уже недоступен по purge deadline API; физическая очистка S10. Live Telegram пока NOT_RUN.

## Решения

Ledger correction — отдельный signed compensating entry со ссылкой на original и причиной, не автоматический физический refund. Реальные возвраты вид kind=refund. Все ledger amounts положительные, direction ±1; баланс не может быть отрицательным или больше лимита. Snapshot JSON не ссылается FK на удаляемые позиции, поэтому история сохраняется. ReceiptDTO в settling/closed берёт calculation из snapshot. Cash command только в settling; перед изменением prices creator явно возвращает collecting. Outbox может доставляться at-least-once; semantic idempotency обеспечена mutations.

## Коммит

Planned subject: feat(settlement): preserve cash and enforce creator close

## Продолжение

S07 — полный мобильный Mini App для ручного workflow и Playwright разных пользователей.

# S04 — Участники и приглашения

Дата UTC: 2026-10-04. Статус: DONE. Базовый HEAD: 7e50b1b.

## Результат

Работают application contacts, request-only ссылки → заявки → owner approval, адресные ссылки с проверкой Telegram ID, повторное принятие без дублей, expiry/revoke и удаление участника без долей. До approval не раскрываются позиции/расчёты/состав. В draft accepted участник видит ожидание открытия. Creator и участник с долями не удаляются; ledger guard добавляется с самой ledger таблицей в S06.

## Изменения

member_models, migration 0003, services/members, api/members и generated TS. Tokens 256-bit random, digest в PostgreSQL, TTL 72 часа; targeted invitation одноразовая. Contacts выводятся только из общих accepted memberships. Mutation чека блокирует receipt, проверяет version, membership changes сбрасывают confirmations.

## Проверки

| Команда / сценарий | Результат | Доказательство |
| --- | --- | --- |
| Alembic revision/upgrade 0003 | PASS | exit 0 |
| make UV=/tmp/receiptsplit-tools/bin/uv api-types check | PASS | exit 0; strict mypy 28 source files; 36 unit + 8 PostgreSQL integration; frontend lint/tsc/test(1)/build |
| Request/approval/contacts/targeted/expiry/revoke/removal | PASS | test_members.py: один длинный API scenario с A/B/D, full ACL и duplicate assertions |
| Empty/previous migrations | PASS | test_migrations.py, 2 schemas до 0003 |
| Live invitations Telegram UI | NOT_RUN | UI links S07/S08; token/HTTPS live gate |
| git diff --check | PASS | exit 0 |

## Критерии приёмки

Новый человек получает доступ после approval; targeted чужой ID запрещён; expired/revoked и повторные приглашения проверены; минимальный preview; accepted list/pending owner requests; данные участника с долями сохраняются. Ledger/report guard выполняется на S06 вместе с созданием денежных таблиц.

## Риски и блокировки

Нет блокировок S04. Invitation creation использует version guard; при потерянном ответе creator отзывает приглашение и создаёт новое. Raw token не сохраняется в idempotency cache/логах. Pending invitations перед settlement должны быть отозваны/использованы, проверка на S06.

## Решения

JoinRequest UNIQUE(receipt,user): после reject возможна новая pending заявка по действующей ссылке; адресная ссылка consumed и не возвращает удалённого member повторно. При revoke pending requests отклоняются. Endpoint review owner принимает/отклоняет; обычная ссылка сама не даёт ACL.

## Коммит

Planned subject: feat(members): add scoped invitations and approval

## Продолжение

S05 — свои доли, take remaining, confirmations и simultaneous PostgreSQL races.

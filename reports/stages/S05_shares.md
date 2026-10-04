# S05 — Доли и конкурентный выбор

Дата UTC: 2026-10-04. Статус: DONE. Базовый HEAD: 1056304.

## Результат

PUT my-share принимает абсолютные bp только для authenticated member в collecting; 0 удаляет запись, overflow и stale version дают 409. Receipt lock общий с CRUD и financial changes. Creator take-remaining явно забирает остаток одной/всех позиций; чужие доли не меняются. Confirm-selection сохраняет текущую financial revision; финансовая правка сбрасывает все confirmations. Calculation возвращает суммы, unassigned, own cost и version/revision.

## Изменения

services/shares.py, api/shares.py, TS contracts и integration test_shares.py. Shares/FK и confirmed_revision созданы заранее на S03, новая миграция не нужна.

## Проверки

| Команда / сценарий | Результат | Доказательство |
| --- | --- | --- |
| make UV=/tmp/receiptsplit-tools/bin/uv api-types check | PASS | exit 0; lint/format/strict mypy 30 source files, 36 unit + 9 real PG integration, frontend lint/tsc/test(1)/build |
| pytest tests/integration/test_shares.py после explicit 100% case | PASS | exit 0; 1 scenario, 0,88 с |
| Два simultaneous пользователя по 60% | PASS | ThreadPoolExecutor + Barrier(2); HTTP responses 200/409, DB sum≤10000 |
| 0/12,34/100%, overflow, member spoof, wrong item, confirm invalidation, owner remaining | PASS | тот же API scenario; 0 row удалён, overflow 409 available_bp=4000, unassigned не в owner debt |
| git diff --check | PASS | exit 0 |

## Критерии приёмки

Все критерии S05 выполнены. Повтор PUT того же абсолютного значения на текущей version не создаёт нового financial change; stale version требует refetch. Unknown body member_id отвергается extra=forbid. Concurrent starts синхронизированы barrier, не являются последовательной симуляцией.

## Риски и блокировки

Нет блокировок S05. UI polling будет подключён на S07; API snapshot consistency обеспечивается shared receipt read lock.

## Решения

Take-remaining изменяет revision один раз на команду, даже для всех строк. Confirm-selection увеличивает version, но сохраняет financial revision и чужие confirmations. Share PUT не допускается в draft/settling/closed.

## Коммит

Planned subject: feat(shares): enforce concurrent share selection

## Продолжение

S06 — immutable snapshot/ledger, report vs receive, edit after money и creator-only close.

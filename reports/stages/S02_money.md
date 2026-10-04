# S02 — Денежное ядро и состояния

Дата UTC: 2026-10-04. Статус: DONE. Базовый HEAD: da1dfbe.

## Результат

- Pure domain Money/ShareBasisPoints/Discount/Tips, exact Decimal parsing, суммы в целых копейках и JSON-compatible сериализация.
- Largest remainder с рациональными остатками и стабильным UUID tie-break; предварительный unassigned, общая скидка, чаевые и доля создателя.
- State/revision guards, проверка реальных полученных денег и возвратов; closed нельзя открыть, participant не может закрыть, reported не заменяет cash.

## Изменения

domain/money.py, domain/states.py и tests/test_money.py. Домен не импортирует HTTP/ORM/bot. Financial revision и version изменяются отдельно. Durable snapshots и transaction-level применение появятся в S03–S06.

## Проверки

| Команда / сценарий | Результат | Доказательство |
| --- | --- | --- |
| make UV=/tmp/receiptsplit-tools/bin/uv check-backend | PASS | exit 0; lint/format (28 files), strict mypy (20 source files), 36 unit tests |
| Все 6 денежных эталонов + E2E-01 calculation | PASS | tests/test_money.py; 990 ₽, 100,01 ₽ tie, 33,33%, preview 247,50/742,50, 100% discount/tips |
| Hypothesis conservation/bounds + permutation | PASS | 300 calculation examples + 100 remainder examples (6 permutations каждого); точные суммы, нулевые доли не получают чаевые |
| Guard close/report/repricing/refund/revision | PASS | explicit state tests; net 500–100=400; under/over/report/participant блокируют close |
| git diff --check | PASS | exit 0 |
| DB/UI/live OCR проверки | NOT_RUN | не менялись DB/API/UI; targeted scope S02 pure domain |

## Критерии приёмки

Все денежные эталоны, conservation, детерминированность, invalid inputs, нулевые доли/чаевые и state guards выполнены. Pure расчёт исключает нулевые share weights; durable удаление записи 0% проверяется на S05. Owner cost не превращается в долг самому себе. expected_from_others = G − own_cost по спецификации; unassigned показывается отдельно и не становится ledger debt.

## Риски и блокировки

Нет блокировок S02. Реальные транзакционные гонки и snapshots будут проверены в S05/S06, где появится DB workflow. Денежный лимит 100 000 000 minor units применяется также к полному итогу с чаевыми.

## Решения

Half-up на целых: (base × bp + 5000) // 10000. Unassigned сортируется после UUID при равных остатках. Каждая строка округляется отдельно; скидка и чаевые распределяются отдельными проходами. При полной скидке фиксированные чаевые используют исходные веса.

## Коммит

Planned subject: feat(money): calculate exact receipt shares

## Продолжение

S03 — PostgreSQL receipts/items/members, ручной CRUD и авторитетный calculation API.

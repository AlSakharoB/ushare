# Прогресс ReceiptSplit

Дата UTC: 2026-10-04. Начальный HEAD отсутствует; ветка master.

| Этап | Статус | Отчёт | Commit subject |
| --- | --- | --- | --- |
| S00 | DONE | stages/S00_foundation.md | chore(project): scaffold services and checks |
| S01 | DONE | stages/S01_auth.md | feat(auth): validate Telegram sessions |
| S02 | DONE | stages/S02_money.md | feat(money): calculate exact receipt shares |
| S03 | DONE | stages/S03_receipts.md | feat(receipts): add manual receipt workflow |
| S04 | DONE | stages/S04_members.md | feat(members): add scoped invitations and approval |
| S05 | DONE | stages/S05_shares.md | feat(shares): enforce concurrent share selection |
| S06–S11 | NOT_STARTED | — | — |

S00 commit: b26ad81.
S01 commit: da1dfbe.
S02 commit: 560176a.
S03 commit: 7e50b1b.
S04 commit: 1056304.

Внешние gates: Telegram token/HTTPS и реальные клиенты для live smoke; разрешённые обезличенные реальные чеки для OCR benchmark. Они не мешают независимой локальной реализации.

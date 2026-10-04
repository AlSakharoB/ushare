# S09 — OCR, проверка позиций и качество

## Вход

Прочитай: 05_OCR_STRATEGY.md, 06_MINI_APP_UX.md, 07_TEST_STRATEGY.md. Порядок зависимостей — `09_ROADMAP.md`.

## Шаги реализации

1. Реальный провайдер PaddleOCR baseline с Cyrillic recognizer и pinned artifact versions/checksums. Изолированный OCR worker; explicit setup model command и отдельный Compose профиль.
2. Upload/crop/rotation/multi-image jobs, lease/timeout/retry/status; без блокирования event loop API. Приём фото из bot и Mini App ведёт в общий pipeline.
3. Preprocessing и parser: bboxes, строки, totals, quantity, discount candidates, confidence/warnings; ошибки и unknown fields безопасны.
4. Реализуй OCR candidate schema, review UI, ручные исправления и явное применить. Версия защиты, повтор apply не дублирует строки; ручные поля не перетираются поздним job.
5. Собери разрешённый реальный dataset/ground truth. Если фото нет — создай synthetic plumbing fixtures, явно запроси реальные чеки и не ставь quality gate PASS.
6. Benchmark baseline vs preprocessing/UVDoc; Qwen3-VL-8B при наличии hardware; PP-OCRv6 при документированной Cyrillic совместимости как optional candidate.
7. Зафиксируй выбранный профиль по точности числовых полей, ресурсам и времени. Таблицы качества по группам, missed/extra rows, dangerous errors, примеры failures.
8. Улучши фактически слабые места; manual/reshoot fallback. Не увеличивай complexity с cloud API без поручения пользователя.

## Проверка и приёмка

- E2E-03 проходит на реальном изображении и рабочем OCR, не на mocked JSON.
- Dataset и честный holdout соответствуют 05_OCR_STRATEGY.
- Есть benchmark CLI, raw safe results и отчёт model/hardware/versions/metrics.
- Целевые gates чисел/recall/latency достигнуты либо этап BLOCKED с точными цифрами; недостигнутые метрики не скрыты.
- Crooked/curved/blur/glare/multipage cases измерены.
- ИНН/НДС/сдача не превращаются в товар, неизвестная сумма не выдумывается.
- Timeout/OOM/missing weights дают безопасный failure + manual mode.

## Артефакты этапа

Рабочий код/миграции/документация по scope; meaningful tests; `reports/stages/S09_ocr.md`; обновлённый `reports/PROGRESS.md`. Для OCR также benchmark artifacts, для UI — безопасные screenshots.

## Завершение

Выполни `08_STAGE_WORKFLOW.md`: проверь diff/секреты, запиши PASS/FAIL/NOT_RUN по каждому критерию, сделай локальный атомарный commit только своих изменений, сообщи SHA и следующий шаг. Не отмечай DONE при незакрытом обязательном критерии. При поручении всего проекта продолжай следующий независимый этап без повторного запроса разрешения.

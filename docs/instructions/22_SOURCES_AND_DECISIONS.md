# Первичные источники и решения

Проверено 03.10.2026. Документация mutable: Codex на соответствующем этапе проверяет актуальное API, фиксирует dependency/model versions и указывает фактические результаты. Ссылки не заменяют tests.

## Telegram

- Mini Apps, initData, signature/freshness, Main Mini App, startapp, themes и viewport: https://core.telegram.org/bots/webapps
- Bot API: https://core.telegram.org/bots/api
- Возможности ботов и deep linking: https://core.telegram.org/bots/features

Вывод для архитектуры: Telegram supplies identity, backend validates signed data. URL context сам по себе не даёт доступа. Mini App и бот — разные каналы одного продукта, уведомления зависят от права бота писать пользователю.

## OCR

- Официальный PaddleOCR repository и история моделей: https://github.com/PaddlePaddle/PaddleOCR
- PP-OCRv5 multilingual models, включая Cyrillic recognizer: https://github.com/PaddlePaddle/PaddleOCR/blob/main/docs/version3.x/algorithm/PP-OCRv5/PP-OCRv5_multi_languages.en.md
- OCR pipeline, orientation/unwarping: https://www.paddleocr.ai/main/en/version3.x/pipeline_usage/OCR.html
- Qwen3-VL-8B-Instruct, официальная карточка: https://huggingface.co/Qwen/Qwen3-VL-8B-Instruct
- Qwen3-VL official repository: https://github.com/QwenLM/Qwen3-VL

Выбор для MVP: локальный PaddleOCR с конкретной кириллической моделью и preprocessing. Более новая версия в текущей документации не основание автоматически менять pinned runtime. Qwen — дополнительный кандидат с отдельным hardware gate. Заявления разработчиков о модели не являются измеренной точностью чеков нашего приложения.

## Архитектурные решения, которые нужно закрепить ADR

1. Модульный Python backend + bot; React Mini App; PostgreSQL — главный источник истины.
2. Деньги в minor units, доли в basis points; largest remainder, проверенные примеры.
3. Creator получает деньги вне приложения; «Перевёл» и «Получено» разные события.
4. CRUD до закрытия через возврат к collecting; cash ledger сохраняется.
5. Private storage и background OCR; review creator перед финансовым использованием.
6. PostgreSQL jobs/outbox до появления обоснования отдельного брокера.
7. Same-origin opaque cookie session + CSRF; dev auth исключён из production.
8. Истечение ровно через 7 суток; endpoints сразу скрывают, worker удаляет физически с оговорённым интервалом.

Это инженерные решения для данного проекта, не универсальные требования Telegram или моделей.

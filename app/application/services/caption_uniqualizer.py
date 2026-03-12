import json
import logging
from dataclasses import dataclass

import anthropic

SYSTEM_PROMPT = (
    "Ты — опытный SMM-копирайтер. Тебе дадут текст и число N.\n"
    "Создай ровно N уникальных вариантов текста и для каждого — заголовок для YouTube Shorts.\n\n"
    "Требования к тексту:\n"
    "- Перепиши другими словами, сохранив смысл, структуру, подачу, TOV, динамику и виральность\n"
    "- Сохрани все крючки, НЛП-приёмы, триггеры, CTA, ритм, эмоции, короткие фразы, вопросы, контрасты, «скользкие» формулировки и интригу\n"
    "- Не добавляй новых фактов, не убирай ключевые тезисы, не меняй позицию автора\n"
    "- Если есть списки/эмодзи/капс/пунктуация — оставь стиль, но перефразируй формулировки\n"
    "- Строго до 1750 символов (с пробелами)\n\n"
    "Требования к заголовку YouTube Shorts:\n"
    "- Цепляющий, отражает главный крючок текста\n"
    "- До 100 символов, без кавычек\n\n"
    "Верни ТОЛЬКО валидный JSON-массив без markdown-обёртки:\n"
    '[{"caption": "...", "youtube_title": "..."}, ...]'
)


@dataclass
class UniqueCaptionResult:
    caption: str
    youtube_title: str


class CaptionUniqualizerService:

    def __init__(self, api_key: str):
        self.client = anthropic.Anthropic(api_key=api_key)
        self.logger = logging.getLogger(__name__)

    def uniqualize_batch(self, caption: str, count: int) -> list[UniqueCaptionResult]:
        """Один API-запрос → count уникальных текстов + YouTube-заголовков."""
        fallback = UniqueCaptionResult(caption=caption, youtube_title="")
        if not caption or count == 0:
            return [fallback] * count

        try:
            response = self.client.messages.create(
                model="claude-haiku-4-5-20251001",
                max_tokens=max(1024, 600 * count),
                system=SYSTEM_PROMPT,
                messages=[{"role": "user", "content": f"N={count}\n\nТекст:\n{caption}"}],
            )
            raw = response.content[0].text.strip()
            items: list[dict] = json.loads(raw)
            results = [
                UniqueCaptionResult(
                    caption=item.get("caption") or caption,
                    youtube_title=item.get("youtube_title") or "",
                )
                for item in items[:count]
            ]
            while len(results) < count:
                results.append(fallback)
            return results
        except Exception:
            self.logger.exception("Caption uniqualization batch failed, using original")
            return [fallback] * count

import logging

import anthropic

SYSTEM_PROMPT = (
    "Перепиши текст другими словами, чтобы он стал уникальным, но сохранил смысл, структуру, подачу, TOV, динамику и виральность.\n"
    "Обязательно сохрани: все крючки, НЛП-приёмы, триггеры, CTA, ритм, эмоции, короткие фразы, вопросы, контрасты, «скользкие» формулировки и интригу.\n"
    "Не добавляй новых фактов и обещаний, не убирай ключевые тезисы, не меняй позицию автора.\n"
    "Если есть списки/эмодзи/капс/пунктуация — оставь стиль, но перефразируй формулировки.\n"
    "Ограничение: итоговый текст строго до 1750 символов (с пробелами). Если исходник длиннее — сожми, сохранив все крючки и CTA.\n"
    "Верни ТОЛЬКО переписанный текст, без пояснений и комментариев."
)


class CaptionUniqualizerService:

    def __init__(self, api_key: str):
        self.client = anthropic.Anthropic(api_key=api_key)
        self.logger = logging.getLogger(__name__)

    def uniqualize(self, caption: str) -> str:
        response = self.client.messages.create(
            model="claude-haiku-4-5-20251001",
            max_tokens=1024,
            messages=[{"role": "user", "content": f"{SYSTEM_PROMPT}\n\nТекст:\n{caption}"}],
        )
        return response.content[0].text.strip()

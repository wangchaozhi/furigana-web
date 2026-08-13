from __future__ import annotations

import json
import os

from openai import OpenAI
from pydantic import BaseModel


DEFAULT_MODEL = "gpt-5.6-terra"


class TranslationOutput(BaseModel):
    translations: list[str]


def configured_model() -> str:
    return os.getenv("OPENAI_TRANSLATION_MODEL", DEFAULT_MODEL).strip() or DEFAULT_MODEL


def is_configured() -> bool:
    return bool(os.getenv("OPENAI_API_KEY", "").strip())


def translate_lines(lines: list[str], target_language: str, client: OpenAI | None = None) -> list[str]:
    nonempty = [(index, line) for index, line in enumerate(lines) if line.strip()]
    if not nonempty:
        return ["" for _ in lines]

    language_name = "Simplified Chinese" if target_language == "zh" else "natural English"
    payload = [{"index": index, "text": line} for index, line in nonempty]
    api = client or OpenAI(timeout=60.0, max_retries=2)
    response = api.responses.parse(
        model=configured_model(),
        instructions=(
            f"Translate Japanese lyrics or prose into {language_name}. "
            "Preserve tone, imagery, names, punctuation, and line-level meaning. "
            "Return exactly one translation for every input item, in the same order. "
            "Do not add explanations, numbering, romanization, or quotation marks."
        ),
        input=json.dumps(payload, ensure_ascii=False),
        text_format=TranslationOutput,
    )
    parsed = response.output_parsed
    if parsed is None or len(parsed.translations) != len(nonempty):
        raise ValueError("The translation service returned an unexpected number of lines")

    translated = ["" for _ in lines]
    for (index, _), text in zip(nonempty, parsed.translations):
        translated[index] = text.strip()
    return translated

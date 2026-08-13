from __future__ import annotations

from .base import TranslationProvider
from .providers import PROVIDERS, OpenAIProvider, TranslationOutput


def get_provider(provider_id: str) -> TranslationProvider:
    try:
        return PROVIDERS[provider_id]()
    except KeyError as error:
        raise ValueError(f"Unknown translation provider: {provider_id}") from error


def available_providers() -> list[dict[str, str | bool]]:
    return [
        {"id": provider.id, "label": provider.label, "configured": provider.configured}
        for provider in (factory() for factory in PROVIDERS.values())
    ]


def translate_lines(
    lines: list[str], target_language: str, provider_id: str = "openai", **kwargs
) -> list[str]:
    provider = get_provider(provider_id)
    translated = provider.translate_lines(lines, target_language, **kwargs)
    if len(translated) != len(lines):
        raise ValueError("The translation service returned an unexpected number of lines")
    return translated


__all__ = ["TranslationOutput", "available_providers", "get_provider", "translate_lines"]

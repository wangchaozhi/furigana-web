"""Compatibility facade for the modular translation providers."""

from .translators import (  # noqa: F401
    TranslationOutput,
    available_providers,
    get_provider,
    translate_lines,
)


def configured_model() -> str:
    provider = get_provider("openai")
    return provider.label


def is_configured(provider: str = "openai") -> bool:
    return get_provider(provider).configured

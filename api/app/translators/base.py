from __future__ import annotations

import json
from abc import ABC, abstractmethod
from typing import Any
from urllib.error import HTTPError, URLError
from urllib.parse import urlencode
from urllib.request import Request, urlopen


class TranslationProvider(ABC):
    id: str
    label: str

    @property
    @abstractmethod
    def configured(self) -> bool: ...

    @abstractmethod
    def translate_lines(self, lines: list[str], target_language: str, **kwargs) -> list[str]: ...

    @staticmethod
    def preserve_blanks(lines: list[str], translate) -> list[str]:
        result = ["" for _ in lines]
        for index, line in enumerate(lines):
            if line.strip():
                result[index] = translate(line).strip()
        return result


def request_json(
    url: str,
    *,
    payload: dict[str, Any] | None = None,
    headers: dict[str, str] | None = None,
    form: dict[str, str] | None = None,
    timeout: float = 60.0,
) -> Any:
    request_headers = dict(headers or {})
    data = None
    if payload is not None:
        data = json.dumps(payload, ensure_ascii=False).encode()
        request_headers.setdefault("Content-Type", "application/json")
    elif form is not None:
        data = urlencode(form).encode()
        request_headers.setdefault("Content-Type", "application/x-www-form-urlencoded")
    try:
        with urlopen(Request(url, data=data, headers=request_headers), timeout=timeout) as response:
            return json.loads(response.read())
    except HTTPError as error:
        detail = error.read().decode(errors="replace")[:500]
        raise ValueError(f"HTTP {error.code}: {detail}") from error
    except (URLError, TimeoutError) as error:
        raise ValueError(f"Translation service connection failed: {error}") from error

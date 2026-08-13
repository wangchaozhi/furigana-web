from __future__ import annotations

import hashlib
import json
import os
import secrets
import time
from typing import Callable
from urllib.parse import urlencode

from openai import OpenAI
from pydantic import BaseModel

from .base import TranslationProvider, request_json


class TranslationOutput(BaseModel):
    translations: list[str]


class OpenAIProvider(TranslationProvider):
    id, label = "openai", "OpenAI（自然翻译）"

    @property
    def configured(self): return bool(os.getenv("OPENAI_API_KEY", "").strip())

    def translate_lines(self, lines, target_language, client: OpenAI | None = None, **_):
        nonempty = [(i, line) for i, line in enumerate(lines) if line.strip()]
        if not nonempty: return ["" for _ in lines]
        language = "Simplified Chinese" if target_language == "zh" else "natural English"
        response = (client or OpenAI(timeout=60, max_retries=2)).responses.parse(
            model=os.getenv("OPENAI_TRANSLATION_MODEL", "gpt-5.6-terra"),
            instructions=f"Translate Japanese lyrics or prose into {language}. Preserve tone, imagery, names, punctuation, and line-level meaning. Return exactly one translation for every input item, in the same order. Do not add explanations, numbering, romanization, or quotation marks.",
            input=json.dumps([{"index": i, "text": text} for i, text in nonempty], ensure_ascii=False),
            text_format=TranslationOutput,
        )
        parsed = response.output_parsed
        if parsed is None or len(parsed.translations) != len(nonempty):
            raise ValueError("The translation service returned an unexpected number of lines")
        result = ["" for _ in lines]
        for (index, _), text in zip(nonempty, parsed.translations): result[index] = text.strip()
        return result


class AzureProvider(TranslationProvider):
    id, label = "azure", "Azure Translator（免费额度大）"
    @property
    def configured(self): return bool(os.getenv("AZURE_TRANSLATOR_KEY", "").strip())
    def translate_lines(self, lines, target_language, transport=request_json, **_):
        endpoint = os.getenv("AZURE_TRANSLATOR_ENDPOINT", "https://api.cognitive.microsofttranslator.com").rstrip("/")
        target = "zh-Hans" if target_language == "zh" else "en"
        headers = {"Ocp-Apim-Subscription-Key": os.environ["AZURE_TRANSLATOR_KEY"]}
        if os.getenv("AZURE_TRANSLATOR_REGION"): headers["Ocp-Apim-Subscription-Region"] = os.environ["AZURE_TRANSLATOR_REGION"]
        data = transport(f"{endpoint}/translate?api-version=3.0&from=ja&to={target}", payload=[{"text": x} for x in lines], headers=headers)
        return [item["translations"][0]["text"].strip() for item in data]


class DeepLProvider(TranslationProvider):
    id, label = "deepl", "DeepL API Free"
    @property
    def configured(self): return bool(os.getenv("DEEPL_API_KEY", "").strip())
    def translate_lines(self, lines, target_language, transport=request_json, **_):
        url = os.getenv("DEEPL_API_URL", "https://api-free.deepl.com/v2/translate")
        target = "ZH-HANS" if target_language == "zh" else "EN"
        data = transport(url, payload={"text": lines, "source_lang": "JA", "target_lang": target}, headers={"Authorization": f"DeepL-Auth-Key {os.environ['DEEPL_API_KEY']}"})
        return [item["text"].strip() for item in data["translations"]]


class GoogleProvider(TranslationProvider):
    id, label = "google", "Google Cloud Translation"
    @property
    def configured(self): return bool(os.getenv("GOOGLE_TRANSLATE_API_KEY", "").strip())
    def translate_lines(self, lines, target_language, transport=request_json, **_):
        url = "https://translation.googleapis.com/language/translate/v2?" + urlencode({"key": os.environ["GOOGLE_TRANSLATE_API_KEY"]})
        data = transport(url, payload={"q": lines, "source": "ja", "target": "zh-CN" if target_language == "zh" else "en", "format": "text"})
        return [item["translatedText"].strip() for item in data["data"]["translations"]]


class LibreProvider(TranslationProvider):
    id, label = "libretranslate", "LibreTranslate（自部署）"
    @property
    def configured(self): return bool(os.getenv("LIBRETRANSLATE_URL", "").strip())
    def translate_lines(self, lines, target_language, transport=request_json, **_):
        url = os.environ["LIBRETRANSLATE_URL"].rstrip("/") + "/translate"
        def one(line):
            payload = {"q": line, "source": "ja", "target": "zh" if target_language == "zh" else "en", "format": "text"}
            if os.getenv("LIBRETRANSLATE_API_KEY"): payload["api_key"] = os.environ["LIBRETRANSLATE_API_KEY"]
            return transport(url, payload=payload)["translatedText"]
        return self.preserve_blanks(lines, one)


class BaiduProvider(TranslationProvider):
    id, label = "baidu", "百度翻译"
    @property
    def configured(self): return bool(os.getenv("BAIDU_TRANSLATE_APP_ID", "").strip() and os.getenv("BAIDU_TRANSLATE_SECRET", "").strip())
    def translate_lines(self, lines, target_language, transport=request_json, **_):
        def one(q):
            salt = secrets.token_hex(8); appid = os.environ["BAIDU_TRANSLATE_APP_ID"]
            sign = hashlib.md5(f"{appid}{q}{salt}{os.environ['BAIDU_TRANSLATE_SECRET']}".encode()).hexdigest()
            data = transport("https://fanyi-api.baidu.com/api/trans/vip/translate", form={"q": q, "from": "jp", "to": "zh" if target_language == "zh" else "en", "appid": appid, "salt": salt, "sign": sign})
            if "error_code" in data: raise ValueError(f"Baidu error {data['error_code']}: {data.get('error_msg', '')}")
            return data["trans_result"][0]["dst"]
        return self.preserve_blanks(lines, one)


class YoudaoProvider(TranslationProvider):
    id, label = "youdao", "有道智云翻译"
    @property
    def configured(self): return bool(os.getenv("YOUDAO_TRANSLATE_APP_KEY", "").strip() and os.getenv("YOUDAO_TRANSLATE_SECRET", "").strip())
    @staticmethod
    def _truncate(q): return q if len(q) <= 20 else q[:10] + str(len(q)) + q[-10:]
    def translate_lines(self, lines, target_language, transport=request_json, **_):
        def one(q):
            salt = secrets.token_hex(8); curtime = str(int(time.time())); key = os.environ["YOUDAO_TRANSLATE_APP_KEY"]
            sign = hashlib.sha256(f"{key}{self._truncate(q)}{salt}{curtime}{os.environ['YOUDAO_TRANSLATE_SECRET']}".encode()).hexdigest()
            data = transport("https://openapi.youdao.com/api", form={"q": q, "from": "ja", "to": "zh-CHS" if target_language == "zh" else "en", "appKey": key, "salt": salt, "sign": sign, "signType": "v3", "curtime": curtime})
            if data.get("errorCode") != "0": raise ValueError(f"Youdao error {data.get('errorCode')}")
            return data["translation"][0]
        return self.preserve_blanks(lines, one)


PROVIDERS: dict[str, Callable[[], TranslationProvider]] = {p.id: p for p in [AzureProvider, LibreProvider, BaiduProvider, YoudaoProvider, GoogleProvider, DeepLProvider, OpenAIProvider]}

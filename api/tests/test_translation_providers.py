from app.translators.providers import AzureProvider, BaiduProvider, DeepLProvider, GoogleProvider, LibreProvider, YoudaoProvider


def test_azure_batches_lines(monkeypatch):
    monkeypatch.setenv("AZURE_TRANSLATOR_KEY", "secret")
    seen = {}
    def transport(url, **kwargs):
        seen.update(url=url, **kwargs)
        return [{"translations": [{"text": "明天"}]}, {"translations": [{"text": "海"}]}]
    assert AzureProvider().translate_lines(["明日", "海"], "zh", transport=transport) == ["明天", "海"]
    assert "to=zh-Hans" in seen["url"]
    assert seen["headers"]["Ocp-Apim-Subscription-Key"] == "secret"


def test_google_batches_lines(monkeypatch):
    monkeypatch.setenv("GOOGLE_TRANSLATE_API_KEY", "secret")
    def transport(url, **kwargs):
        assert "key=secret" in url
        assert kwargs["payload"]["source"] == "ja"
        return {"data": {"translations": [{"translatedText": "Tomorrow"}]}}
    assert GoogleProvider().translate_lines(["明日"], "en", transport=transport) == ["Tomorrow"]


def test_deepl_batches_lines(monkeypatch):
    monkeypatch.setenv("DEEPL_API_KEY", "secret")
    def transport(_, **kwargs):
        assert kwargs["headers"]["Authorization"] == "DeepL-Auth-Key secret"
        return {"translations": [{"text": "明天"}]}
    assert DeepLProvider().translate_lines(["明日"], "zh", transport=transport) == ["明天"]


def test_libre_preserves_blank_lines(monkeypatch):
    monkeypatch.setenv("LIBRETRANSLATE_URL", "http://translate.local")
    def transport(url, **kwargs):
        assert url == "http://translate.local/translate"
        return {"translatedText": "明天"}
    assert LibreProvider().translate_lines(["明日", ""], "zh", transport=transport) == ["明天", ""]


def test_baidu_signs_each_nonblank_line(monkeypatch):
    monkeypatch.setenv("BAIDU_TRANSLATE_APP_ID", "app")
    monkeypatch.setenv("BAIDU_TRANSLATE_SECRET", "secret")
    def transport(_, **kwargs):
        assert len(kwargs["form"]["sign"]) == 32
        return {"trans_result": [{"dst": "明天"}]}
    assert BaiduProvider().translate_lines(["明日", ""], "zh", transport=transport) == ["明天", ""]


def test_youdao_uses_v3_signature(monkeypatch):
    monkeypatch.setenv("YOUDAO_TRANSLATE_APP_KEY", "app")
    monkeypatch.setenv("YOUDAO_TRANSLATE_SECRET", "secret")
    def transport(_, **kwargs):
        assert kwargs["form"]["signType"] == "v3"
        assert len(kwargs["form"]["sign"]) == 64
        return {"errorCode": "0", "translation": ["明天"]}
    assert YoudaoProvider().translate_lines(["明日"], "zh", transport=transport) == ["明天"]

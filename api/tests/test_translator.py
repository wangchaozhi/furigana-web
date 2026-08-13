from types import SimpleNamespace

from app.translator import TranslationOutput, translate_lines


class FakeResponses:
    def __init__(self, translations):
        self.translations = translations
        self.kwargs = None

    def parse(self, **kwargs):
        self.kwargs = kwargs
        return SimpleNamespace(output_parsed=TranslationOutput(translations=self.translations))


def test_translate_lines_preserves_blank_line_positions():
    responses = FakeResponses(["明天", "看不见"])
    client = SimpleNamespace(responses=responses)

    result = translate_lines(["明日", "", "見えなくて"], "zh", client=client)

    assert result == ["明天", "", "看不见"]
    assert responses.kwargs["text_format"] is TranslationOutput


def test_translate_lines_rejects_wrong_output_count():
    responses = FakeResponses(["only one"])
    client = SimpleNamespace(responses=responses)

    try:
        translate_lines(["明日", "見えなくて"], "en", client=client)
    except ValueError as error:
        assert "unexpected number" in str(error)
    else:
        raise AssertionError("Expected translation count validation to fail")

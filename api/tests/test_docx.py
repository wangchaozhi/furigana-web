from io import BytesIO
from zipfile import ZipFile

from app.exporters.docx import build_docx
from app.models import AnnotatedLine, DocumentMeta, ExportDocxRequest, LayoutSettings, Segment


def test_docx_contains_native_ruby_xml():
    payload = ExportDocxRequest(
        meta=DocumentMeta(title="Light Dance", artist="Sakanaction", year="2009"),
        lines=[AnnotatedLine(source="明日", segments=[Segment(text="明日", ruby="あした")])],
    )
    data = build_docx(payload)
    with ZipFile(BytesIO(data)) as zf:
        xml = zf.read("word/document.xml").decode("utf-8")
    assert "<w:ruby>" in xml
    assert "<w:rt>" in xml
    assert "<w:rubyBase>" in xml
    assert "あした" in xml
    assert "明日" in xml


def test_docx_applies_layout_settings():
    payload = ExportDocxRequest(
        layout=LayoutSettings(font_size=20, ruby_scale=0.5, font_family="mincho", vertical=True),
        lines=[AnnotatedLine(source="明日", segments=[Segment(text="明日", ruby="あした")])],
    )
    data = build_docx(payload)
    with ZipFile(BytesIO(data)) as zf:
        xml = zf.read("word/document.xml").decode("utf-8")
    assert 'w:val="tbRl"' in xml
    assert 'w:eastAsia="Yu Mincho"' in xml
    assert '<w:hpsBaseText w:val="40"' in xml


def test_docx_includes_enabled_translation():
    payload = ExportDocxRequest(
        translation_language="zh",
        lines=[
            AnnotatedLine(
                source="明日",
                translation="明天",
                segments=[Segment(text="明日", ruby="あした")],
            )
        ],
    )
    data = build_docx(payload)
    with ZipFile(BytesIO(data)) as zf:
        xml = zf.read("word/document.xml").decode("utf-8")
    assert "明天" in xml

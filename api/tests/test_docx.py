from io import BytesIO
from xml.etree import ElementTree
from zipfile import ZipFile

from docx import Document

from app.exporters.docx import build_docx
from app.models import AnnotatedLine, DocumentMeta, ExportDocxRequest, LayoutSettings, Segment


WORD_NS = "http://schemas.openxmlformats.org/wordprocessingml/2006/main"
NS = {"w": WORD_NS}


def _document_root(data: bytes):
    with ZipFile(BytesIO(data)) as zf:
        return ElementTree.fromstring(zf.read("word/document.xml"))


def _local_name(element) -> str:
    return element.tag.rsplit("}", 1)[-1]


def test_docx_contains_native_ruby_xml():
    payload = ExportDocxRequest(
        meta=DocumentMeta(title="Light Dance", artist="Sakanaction", year="2009"),
        lines=[AnnotatedLine(source="明日", segments=[Segment(text="明日", ruby="あした")])],
    )
    data = build_docx(payload)
    root = _document_root(data)
    ruby_elements = root.findall(".//w:ruby", NS)
    nested_ruby_elements = root.findall(".//w:p/w:r/w:ruby", NS)
    assert len(ruby_elements) == 1
    assert len(nested_ruby_elements) == len(ruby_elements)
    assert root.find(".//w:p/w:ruby", NS) is None
    assert ruby_elements[0].find("w:rt/w:r/w:t", NS).text == "あした"
    assert ruby_elements[0].find("w:rubyBase/w:r/w:t", NS).text == "明日"
    assert ruby_elements[0].find("w:rubyPr/w:hpsBaseText", NS).get(f"{{{WORD_NS}}}val") == "27"
    assert ruby_elements[0].find("w:rubyPr/w:hpsRaise", NS).get(f"{{{WORD_NS}}}val") == "25"

    # A parser round-trip catches packaging/XML regressions as well as the
    # targeted hierarchy assertions above.
    Document(BytesIO(data))


def test_docx_applies_layout_settings():
    payload = ExportDocxRequest(
        layout=LayoutSettings(font_size=20, ruby_scale=0.5, font_family="mincho", vertical=True),
        lines=[AnnotatedLine(source="明日", segments=[Segment(text="明日", ruby="あした")])],
    )
    data = build_docx(payload)
    root = _document_root(data)
    section = root.find(".//w:sectPr", NS)
    children = [_local_name(child) for child in section]
    columns = section.findall("w:cols", NS)
    assert len(columns) == 1
    assert columns[0].get(f"{{{WORD_NS}}}num") == "1"
    assert section.find("w:textDirection", NS).get(f"{{{WORD_NS}}}val") == "tbRl"
    assert children.index("cols") < children.index("textDirection") < children.index("docGrid")

    with ZipFile(BytesIO(data)) as zf:
        xml = zf.read("word/document.xml").decode("utf-8")
    assert 'w:eastAsia="Yu Mincho"' in xml
    assert '<w:hpsBaseText w:val="30"' in xml
    assert '<w:hpsRaise w:val="28"' in xml


def test_docx_applies_two_column_layout():
    payload = ExportDocxRequest(
        layout=LayoutSettings(columns=2),
        lines=[AnnotatedLine(source="明日", segments=[Segment(text="明日", ruby="あした")])],
    )
    data = build_docx(payload)
    root = _document_root(data)
    section = root.find(".//w:sectPr", NS)
    children = [_local_name(child) for child in section]
    columns = section.findall("w:cols", NS)
    assert len(columns) == 1
    assert columns[0].get(f"{{{WORD_NS}}}num") == "2"
    assert columns[0].get(f"{{{WORD_NS}}}space") == "540"
    assert columns[0].get(f"{{{WORD_NS}}}sep") == "1"
    assert children.index("cols") < children.index("docGrid")


def test_docx_uses_explicit_a4_page_size():
    payload = ExportDocxRequest(
        lines=[AnnotatedLine(source="明日", segments=[Segment(text="明日", ruby="あした")])],
    )
    root = _document_root(build_docx(payload))
    page_size = root.find(".//w:sectPr/w:pgSz", NS)
    assert page_size.get(f"{{{WORD_NS}}}w") == "11906"
    assert page_size.get(f"{{{WORD_NS}}}h") == "16838"


def test_docx_keeps_title_block_outside_two_column_body():
    payload = ExportDocxRequest(
        meta=DocumentMeta(title="Light Dance", artist="Sakanaction", year="2009"),
        layout=LayoutSettings(columns=2),
        lines=[AnnotatedLine(source="明日", segments=[Segment(text="明日", ruby="あした")])],
    )
    root = _document_root(build_docx(payload))
    sections = root.findall(".//w:sectPr", NS)
    assert len(sections) == 2
    assert sections[0].find("w:cols", NS).get(f"{{{WORD_NS}}}num") == "1"
    assert sections[0].find("w:textDirection", NS) is None
    assert sections[1].find("w:cols", NS).get(f"{{{WORD_NS}}}num") == "2"


def test_docx_starts_vertical_body_on_a_new_page_after_title():
    payload = ExportDocxRequest(
        meta=DocumentMeta(title="Light Dance", artist="Sakanaction", year="2009"),
        layout=LayoutSettings(vertical=True),
        lines=[AnnotatedLine(source="明日", segments=[Segment(text="明日", ruby="あした")])],
    )
    root = _document_root(build_docx(payload))
    sections = root.findall(".//w:sectPr", NS)
    assert len(sections) == 2
    assert sections[0].find("w:textDirection", NS) is None
    assert sections[1].find("w:type", NS).get(f"{{{WORD_NS}}}val") == "nextPage"
    assert sections[1].find("w:textDirection", NS).get(f"{{{WORD_NS}}}val") == "tbRl"


def test_docx_keeps_source_and_translation_together():
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
    root = _document_root(build_docx(payload))
    body_paragraphs = root.findall("./w:body/w:p", NS)
    source_props = body_paragraphs[0].find("w:pPr", NS)
    translation_props = body_paragraphs[1].find("w:pPr", NS)
    assert source_props.find("w:keepNext", NS) is not None
    assert source_props.find("w:keepLines", NS) is not None
    assert translation_props.find("w:keepLines", NS) is not None
    assert source_props.find("w:spacing", NS).get(f"{{{WORD_NS}}}line") == "675"
    assert source_props.find("w:spacing", NS).get(f"{{{WORD_NS}}}lineRule") == "atLeast"
    assert translation_props.find("w:spacing", NS).get(f"{{{WORD_NS}}}line") == "282"
    assert translation_props.find("w:spacing", NS).get(f"{{{WORD_NS}}}lineRule") == "atLeast"


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

from __future__ import annotations

from io import BytesIO

from docx import Document
from docx.enum.text import WD_ALIGN_PARAGRAPH
from docx.oxml import OxmlElement
from docx.oxml.ns import qn
from docx.shared import Inches, Pt

from ..models import ExportDocxRequest, Segment


def _set_run_fonts(run, east_asia: str = "Yu Gothic") -> None:
    run.font.name = "Arial"
    run.font.size = Pt(12)
    r_pr = run._element.get_or_add_rPr()
    r_fonts = r_pr.rFonts
    if r_fonts is None:
        r_fonts = OxmlElement("w:rFonts")
        r_pr.insert(0, r_fonts)
    r_fonts.set(qn("w:ascii"), "Arial")
    r_fonts.set(qn("w:hAnsi"), "Arial")
    r_fonts.set(qn("w:eastAsia"), east_asia)


def _text_element(text: str) -> OxmlElement:
    t = OxmlElement("w:t")
    if text.startswith(" ") or text.endswith(" ") or "  " in text:
        t.set(qn("xml:space"), "preserve")
    t.text = text
    return t


def _run_xml(text: str, size_half_points: int = 24) -> OxmlElement:
    r = OxmlElement("w:r")
    r_pr = OxmlElement("w:rPr")
    fonts = OxmlElement("w:rFonts")
    fonts.set(qn("w:ascii"), "Arial")
    fonts.set(qn("w:hAnsi"), "Arial")
    fonts.set(qn("w:eastAsia"), "Yu Gothic")
    r_pr.append(fonts)
    sz = OxmlElement("w:sz")
    sz.set(qn("w:val"), str(size_half_points))
    r_pr.append(sz)
    sz_cs = OxmlElement("w:szCs")
    sz_cs.set(qn("w:val"), str(size_half_points))
    r_pr.append(sz_cs)
    r.append(r_pr)
    r.append(_text_element(text))
    return r


def _append_ruby(paragraph, base: str, ruby_text: str) -> None:
    ruby = OxmlElement("w:ruby")

    ruby_pr = OxmlElement("w:rubyPr")
    align = OxmlElement("w:rubyAlign")
    align.set(qn("w:val"), "center")
    ruby_pr.append(align)

    hps = OxmlElement("w:hps")
    hps.set(qn("w:val"), "16")  # 8 pt ruby
    ruby_pr.append(hps)

    hps_raise = OxmlElement("w:hpsRaise")
    hps_raise.set(qn("w:val"), "0")
    ruby_pr.append(hps_raise)

    hps_base = OxmlElement("w:hpsBaseText")
    hps_base.set(qn("w:val"), "24")  # 12 pt base
    ruby_pr.append(hps_base)

    lid = OxmlElement("w:lid")
    lid.set(qn("w:val"), "ja-JP")
    ruby_pr.append(lid)
    ruby.append(ruby_pr)

    rt = OxmlElement("w:rt")
    rt.append(_run_xml(ruby_text, 16))
    ruby.append(rt)

    ruby_base = OxmlElement("w:rubyBase")
    ruby_base.append(_run_xml(base, 24))
    ruby.append(ruby_base)

    paragraph._p.append(ruby)


def _append_segment(paragraph, seg: Segment) -> None:
    if seg.ruby:
        _append_ruby(paragraph, seg.text, seg.ruby)
    elif seg.text:
        run = paragraph.add_run(seg.text)
        _set_run_fonts(run)


def build_docx(request: ExportDocxRequest) -> bytes:
    document = Document()
    section = document.sections[0]
    section.top_margin = Inches(0.7)
    section.bottom_margin = Inches(0.7)
    section.left_margin = Inches(0.8)
    section.right_margin = Inches(0.8)

    normal = document.styles["Normal"]
    normal.font.name = "Arial"
    normal.font.size = Pt(12)
    normal._element.rPr.rFonts.set(qn("w:eastAsia"), "Yu Gothic")

    if request.meta.title:
        title = document.add_paragraph()
        title.paragraph_format.space_after = Pt(2)
        run = title.add_run(request.meta.title)
        run.bold = True
        run.font.size = Pt(22)
        _set_run_fonts(run)
        run.font.size = Pt(22)

    subtitle_parts = []
    if request.meta.artist:
        subtitle_parts.append(f"Song by {request.meta.artist}")
    if request.meta.year:
        subtitle_parts.append(request.meta.year)
    if subtitle_parts:
        sub = document.add_paragraph(" · ".join(subtitle_parts))
        sub.paragraph_format.space_after = Pt(14)
        for run in sub.runs:
            _set_run_fonts(run)
            run.font.size = Pt(10.5)

    for line in request.lines:
        p = document.add_paragraph()
        p.paragraph_format.space_after = Pt(2)
        p.paragraph_format.line_spacing = 1.5
        if not line.segments:
            p.add_run("")
            continue
        for seg in line.segments:
            _append_segment(p, seg)

    stream = BytesIO()
    document.save(stream)
    return stream.getvalue()

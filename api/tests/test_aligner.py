from app.analyzer.aligner import align_surface_reading


def compact(surface: str, reading: str):
    return [(x.text, x.ruby) for x in align_surface_reading(surface, reading)]


def test_okurigana():
    assert compact("白い", "シロイ") == [("白", "しろ"), ("い", None)]


def test_verb():
    assert compact("握り", "ニギリ") == [("握", "にぎ"), ("り", None)]


def test_compound():
    assert compact("明日", "アシタ") == [("明日", "あした")]


def test_prefix_kana():
    assert compact("お茶", "オチャ") == [("お", None), ("茶", "ちゃ")]


def test_kana_only():
    assert compact("デジャヴ", "デジャヴ") == [("デジャヴ", None)]

from app.analyzer.sudachi import SudachiAnnotator


def test_ambiguous_word_includes_dictionary_candidates():
    line = SudachiAnnotator().annotate("明日", [])[0]
    segment = next(item for item in line.segments if item.text == "明日")

    assert segment.ruby in segment.candidates
    assert {"あす", "あした", "みょうにち"}.issubset(set(segment.candidates))
    assert segment.confidence == "medium"

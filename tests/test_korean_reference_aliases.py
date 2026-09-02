from app.references import expand_reference, normalize_reference, parse_reference


def test_korean_short_alias_normalizes_to_canonical_code():
    assert normalize_reference("요 8:32") == "JHN 8:32"
    assert normalize_reference("롬 8:1") == "ROM 8:1"
    assert normalize_reference("고전 13:4") == "1CO 13:4"


def test_korean_full_book_name_and_range_are_supported():
    parsed = parse_reference("요한복음 8:31-32")
    assert (parsed.book, parsed.chapter, parsed.start_verse, parsed.end_verse) == ("JHN", 8, 31, 32)
    assert expand_reference("요한복음 8:31-32") == ["JHN 8:31", "JHN 8:32"]


def test_korean_old_testament_alias_uses_hebrew_source_code():
    from app.references import primary_original_language

    assert normalize_reference("사 41:10") == "ISA 41:10"
    assert primary_original_language("사 41:10") == "he"

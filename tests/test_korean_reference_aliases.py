from app.references import expand_reference, normalize_reference, normalize_user_reference, parse_reference


def test_user_reference_collapses_duplicate_point_suffixes_to_registered_range():
    noisy = "야고보서 4:1-10 과 야고보서 4:1, 야고보서 4:1-10 과 야고보서 4:2"
    assert normalize_user_reference(noisy) == "JAS 4:1-10"


def test_user_reference_rejects_distinct_ranges_instead_of_guessing():
    try:
        normalize_user_reference("야고보서 4:1-10 과 로마서 8:1")
    except ValueError as exc:
        assert "서로 다른 책·장" in str(exc)
    else:
        raise AssertionError("서로 다른 중심본문 범위를 자동 병합하면 안 됩니다.")


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

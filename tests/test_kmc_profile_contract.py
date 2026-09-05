from pathlib import Path


PROFILE_ROOT = Path(__file__).parents[1] / "profiles" / "denominations" / "kmc"


def _read(name):
    return (PROFILE_ROOT / name).read_text(encoding="utf-8")


def test_kmc_profile_is_reference_only_and_versioned():
    profile = _read("profile.yaml")
    assert "code: KMC" in profile
    assert "effective_edition: '2025'" in profile
    assert "historical_editions:" in profile and "  - '2021'" in profile
    assert "copyright_status: RESTRICTED" in profile
    assert "indexing_allowed: false" in profile
    assert "fulltext_storage_allowed: false" in profile


def test_kmc_sources_keep_official_urls_without_fulltext_indexing():
    sources = _read("sources.yaml")
    assert sources.count("authority_level: official") == 4
    assert sources.count("reference_mode: official_web_reference") == 4
    assert sources.count("indexable: false") == 4
    assert "pid=195598" in sources
    assert "pid=195597" in sources
    assert "pid=195596" in sources


def test_kmc_discernment_requires_context_and_scripture_first():
    discernment = _read("discernment.yaml")
    assert "keyword_only_decision: false" in discernment
    assert "  - SCRIPTURE" in discernment
    assert "  - context" in discernment
    assert "  - human_review" in discernment
    assert "  - 성화" in discernment

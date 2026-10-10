import sqlite3

from app.application.canary_builders import StructureBuilder
from app.application.research_section_service import ResearchSectionService
from app.application.section_contracts import SectionRegenerationRequest
from app.migrations import apply_research_sections_migration
from app.repositories.research_sections import ResearchSectionRepository


def _service(tmp_path, loader):
    db = tmp_path / "bible.db"
    with sqlite3.connect(db) as con:
        con.execute(
            "CREATE TABLE sermons (id INTEGER PRIMARY KEY AUTOINCREMENT, topic TEXT NOT NULL, created_at TEXT NOT NULL)"
        )
        con.execute("INSERT INTO sermons(topic, created_at) VALUES('테스트', datetime('now'))")
    apply_research_sections_migration(db)
    repository = ResearchSectionRepository(db)
    service = ResearchSectionService(repository, {"structure": StructureBuilder(loader)})
    return repository, service


def _request():
    return SectionRegenerationRequest(
        "structure",
        {"reference": "테스트 1:1"},
        {"source_ids": ["source-1"], "citation_coverage": 1.0},
        "source-snapshot-1",
    )


def _ready_study(reference, related):
    return {
        "translations": [{"reference": reference, "translation": "TEST", "text": "중심 본문"}],
        "context": [],
        "related": list(related or []),
        "warnings": [],
        "counts": {"translations": 1, "context": 0, "related": len(related or [])},
    }


def test_service_persists_ready_structure_as_first_version(tmp_path):
    repository, service = _service(tmp_path, _ready_study)

    result = service.generate(1, _request())

    assert result["build"]["status"] == "ready"
    assert result["section"]["version"] == 1
    assert result["section"]["status"] == "ready"
    assert result["section"]["content"]["reference"] == "테스트 1:1"
    assert repository.latest(1, "structure")["source_snapshot_id"] == "source-snapshot-1"


def test_service_records_missing_main_passage_as_insufficient_evidence(tmp_path):
    repository, service = _service(
        tmp_path,
        lambda reference, related: {
            "translations": [], "context": [], "related": [],
            "warnings": ["중심본문 없음"], "counts": {},
        },
    )

    result = service.generate(1, _request())

    assert result["build"]["status"] == "invalid"
    assert result["section"]["status"] == "insufficient_evidence"
    assert result["section"]["quality_status"] == "warning"
    assert "registered main-passage text is required" in result["section"]["content"]["errors"]
    assert repository.latest(1, "structure")["version"] == 1


def test_service_isolates_builder_failure_and_retry_creates_new_version(tmp_path):
    attempts = 0

    def flaky_loader(reference, related):
        nonlocal attempts
        attempts += 1
        if attempts == 1:
            raise RuntimeError("temporary builder failure")
        return _ready_study(reference, related)

    repository, service = _service(tmp_path, flaky_loader)
    request = _request()

    failed = service.generate(1, request)
    retried = service.retry(1, request)

    assert failed["section"]["version"] == 1
    assert failed["section"]["status"] == "failed"
    assert failed["section"]["content"]["attempt"] == 0
    assert retried["section"]["version"] == 2
    assert retried["section"]["status"] == "ready"
    versions = repository.list_versions(1, "structure")
    assert [item["status"] for item in versions] == ["ready", "failed"]


def test_service_rejects_unknown_builder_and_bad_coverage_without_writes(tmp_path):
    builder_calls = 0

    def counted_loader(reference, related):
        nonlocal builder_calls
        builder_calls += 1
        return _ready_study(reference, related)

    repository, service = _service(tmp_path, counted_loader)

    unknown = SectionRegenerationRequest("verse_commentary", {"reference": "테스트 1:1"}, {})
    try:
        service.generate(1, unknown)
    except ValueError as exc:
        assert "builder is not registered" in str(exc)
    else:
        raise AssertionError("unregistered builder was accepted")

    bad_coverage = SectionRegenerationRequest(
        "structure", {"reference": "테스트 1:1"}, {"citation_coverage": "unknown"}
    )
    try:
        service.generate(1, bad_coverage)
    except ValueError as exc:
        assert "citation_coverage must be numeric" in str(exc)
    else:
        raise AssertionError("non-numeric coverage was accepted")

    out_of_range = SectionRegenerationRequest(
        "structure", {"reference": "테스트 1:1"}, {"citation_coverage": 1.1}
    )
    try:
        service.generate(1, out_of_range)
    except ValueError as exc:
        assert "citation_coverage must be between 0 and 1" in str(exc)
    else:
        raise AssertionError("out-of-range coverage was accepted")

    assert builder_calls == 0
    assert repository.list_versions(1, "structure") == []


def test_service_checks_schema_before_builder_execution(tmp_path):
    db = tmp_path / "bible.db"
    with sqlite3.connect(db) as con:
        con.execute(
            "CREATE TABLE sermons (id INTEGER PRIMARY KEY AUTOINCREMENT, topic TEXT NOT NULL, created_at TEXT NOT NULL)"
        )
    builder_calls = 0

    def loader(reference, related):
        nonlocal builder_calls
        builder_calls += 1
        return _ready_study(reference, related)

    service = ResearchSectionService(
        ResearchSectionRepository(db), {"structure": StructureBuilder(loader)}
    )
    try:
        service.generate(1, _request())
    except RuntimeError as exc:
        assert "migration is required" in str(exc)
    else:
        raise AssertionError("missing migration was accepted")
    assert builder_calls == 0

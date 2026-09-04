from app.application import scripture_facade


def test_scripture_facade_preserves_legacy_contract(monkeypatch):
    monkeypatch.setattr(scripture_facade, "original_language_coverage", lambda reference: {"reference": reference})
    monkeypatch.setattr(scripture_facade, "bible_database_dashboard", lambda: {"passages": 3})
    monkeypatch.setattr(scripture_facade, "bible_database_integrity", lambda: {"ok": True})
    monkeypatch.setattr(scripture_facade, "compare_reference", lambda reference: [{"reference": reference}])
    monkeypatch.setattr(scripture_facade, "import_items", lambda items: len(items))

    assert scripture_facade.original_coverage("요 3:16")["reference"] == "요 3:16"
    assert scripture_facade.database_dashboard() == {"passages": 3}
    assert scripture_facade.database_integrity() == {"ok": True}
    assert scripture_facade.compare("요 3:16") == [{"reference": "요 3:16"}]
    assert scripture_facade.import_passages([{"text": "본문"}]) == 1

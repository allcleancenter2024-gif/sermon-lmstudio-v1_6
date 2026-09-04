from app.application import doctrine_facade


def test_doctrine_facade_preserves_approval_and_license_boundaries(monkeypatch):
    monkeypatch.setattr(doctrine_facade, "add_doctrine_chunk", lambda payload: 7)
    monkeypatch.setattr(doctrine_facade, "fetch_indexable_doctrine_chunks", lambda db: [{"id": 1}])
    monkeypatch.setattr(doctrine_facade, "transition_document", lambda *args: {"review_status": "APPROVED"})
    monkeypatch.setattr(doctrine_facade, "register_translation_license", lambda payload: None)
    monkeypatch.setattr(doctrine_facade, "translation_licenses", lambda: [{"translation": "WEB"}])

    assert doctrine_facade.create_chunk({"text": "근거"}) == 7
    assert doctrine_facade.indexable_chunks() == [{"id": 1}]
    assert doctrine_facade.review_document(1, actor="admin", comment="확인") == {"review_status": "APPROVED"}
    doctrine_facade.create_license({"translation": "WEB"})
    assert doctrine_facade.list_licenses() == [{"translation": "WEB"}]

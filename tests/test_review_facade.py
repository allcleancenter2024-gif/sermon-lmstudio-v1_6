from app.application import review_facade


def test_review_facade_exposes_all_review_gates():
    for name in (
        "save_sermon", "sermon_versions", "compare_sermon_versions",
        "get_generation_audit", "add_sermon_review", "reaudit_sermon_version",
        "lock_sermon_version", "revision_suggestions", "apply_revision_suggestions",
    ):
        assert getattr(review_facade, name) is not None

from app.application import exports_facade


def test_exports_facade_preserves_approved_output_contract():
    for name in (
        "sermon_document", "dashboard_html", "write_docx", "write_pdf",
        "write_final_package", "with_legacy_fallback", "select_output",
    ):
        assert getattr(exports_facade, name) is not None

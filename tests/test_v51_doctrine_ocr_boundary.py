import sys
import types
import unittest
from unittest.mock import patch

from app.doctrine_processing import DoctrineQualityError, extract_pdf


class _EmptyPage:
    def extract_text(self):
        return ""


class _EmptyReader:
    def __init__(self, _stream):
        self.pages = [_EmptyPage(), _EmptyPage()]


class DoctrineOcrBoundaryTests(unittest.TestCase):
    def test_scan_pdf_is_rejected_for_ocr_review_instead_of_indexing_empty_text(self):
        fake_pypdf = types.SimpleNamespace(PdfReader=_EmptyReader)
        with patch.dict(sys.modules, {"pypdf": fake_pypdf}):
            with self.assertRaisesRegex(DoctrineQualityError, "OCR 검토"):
                extract_pdf(b"scan-pdf-placeholder")


if __name__ == "__main__":
    unittest.main()

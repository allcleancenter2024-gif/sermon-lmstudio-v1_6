import unittest
from unittest.mock import patch

from app.doctrine_ocr import (
    DisabledOcrProvider,
    OcrResult,
    OcrUnavailable,
    TesseractOcrProvider,
    check_tesseract_readiness,
    ocr_min_confidence,
    validate_ocr_result,
)


class DoctrineOcrProviderTests(unittest.TestCase):
    def test_ocr_is_disabled_by_default_provider(self):
        with self.assertRaises(OcrUnavailable):
            DisabledOcrProvider().extract(b"scan")

    def test_confidence_policy_accepts_valid_result(self):
        result = OcrResult("본문", 0.9, 1, "test")
        validate_ocr_result(result, minimum_confidence=0.85)
        self.assertEqual(ocr_min_confidence({"DOCTRINE_OCR_MIN_CONFIDENCE": "0.8"}), 0.8)

    def test_confidence_below_policy_is_rejected(self):
        with self.assertRaisesRegex(ValueError, "confidence"):
            validate_ocr_result(OcrResult("본문", 0.4, 1, "test"), minimum_confidence=0.85)

    def test_tesseract_rejects_pdf_before_external_execution(self):
        provider = TesseractOcrProvider(command="tesseract")
        with patch("app.doctrine_ocr.subprocess.run") as run:
            with self.assertRaisesRegex(OcrUnavailable, "이미지 입력만"):
                provider.extract(b"pdf", "application/pdf")
            run.assert_not_called()

    def test_tesseract_parses_tsv_without_shell_execution(self):
        tsv = (
            b"level\tpage_num\tblock_num\tpar_num\tline_num\tword_num\tleft\ttop\twidth\theight\tconf\ttext\n"
            b"5\t1\t1\t1\t1\t1\t0\t0\t10\t10\t95.0\t\xec\x98\x88\n"
            b"5\t1\t1\t1\t1\t2\t0\t0\t10\t10\t85.0\t\xec\x84\xb1\n"
        )
        completed = unittest.mock.Mock(returncode=0, stdout=tsv, stderr=b"")
        with patch("app.doctrine_ocr.subprocess.run", return_value=completed) as run:
            result = TesseractOcrProvider(command="tesseract", languages="heb+grc").extract(
                b"image", "image/png"
            )
        self.assertEqual(result.text, "예 성")
        self.assertAlmostEqual(result.confidence, 0.9)
        self.assertEqual(run.call_args.kwargs["shell"], False)
        self.assertEqual(run.call_args.kwargs["timeout"], 120)
        self.assertIn("--psm", run.call_args.args[0])
        self.assertIn("6", run.call_args.args[0])

    def test_tesseract_page_segmentation_mode_is_configurable(self):
        provider = TesseractOcrProvider(command="tesseract", page_segmentation_mode=7)
        self.assertEqual(provider.page_segmentation_mode, 7)
        with self.assertRaisesRegex(ValueError, "3부터 13"):
            TesseractOcrProvider(page_segmentation_mode=2)

    def test_tessdata_directory_is_explicitly_passed_when_configured(self):
        completed = unittest.mock.Mock(returncode=0, stdout=b"level\tconf\ttext\n", stderr=b"")
        with patch("app.doctrine_ocr.subprocess.run", return_value=completed) as run:
            TesseractOcrProvider(tessdata_dir=r"C:\\ocr-models").extract(b"image", "image/png")
        args = run.call_args.args[0]
        self.assertIn("--tessdata-dir", args)
        self.assertIn(r"C:\\ocr-models", args)

    def test_tesseract_readiness_reports_missing_binary_without_installing(self):
        readiness = check_tesseract_readiness(command="missing-tesseract")
        self.assertFalse(readiness.available)
        self.assertEqual(readiness.missing_languages, ("heb", "grc"))
        self.assertIn("준비되지 않았습니다", readiness.message)

    def test_tesseract_readiness_checks_required_language_data(self):
        version = unittest.mock.Mock(returncode=0, stdout=b"tesseract 5.5.0\n", stderr=b"")
        langs = unittest.mock.Mock(returncode=0, stdout=b"List of available languages in \"/tmp\":\neng\nheb\n", stderr=b"")
        with patch("app.doctrine_ocr.subprocess.run", side_effect=[version, langs]) as run:
            readiness = check_tesseract_readiness(command="tesseract", required_languages=("heb", "grc"))
        self.assertFalse(readiness.available)
        self.assertEqual(readiness.missing_languages, ("grc",))
        self.assertEqual(run.call_count, 2)
        self.assertFalse(any(call.kwargs.get("shell") for call in run.call_args_list))


if __name__ == "__main__":
    unittest.main()

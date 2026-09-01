from __future__ import annotations

import asyncio
import io
import unittest
import zipfile

from fastapi import HTTPException

import app.main as main
from app.importers import convert_usfm_zip


def make_zip(files: dict[str, str]) -> bytes:
    buffer = io.BytesIO()
    with zipfile.ZipFile(buffer, "w", compression=zipfile.ZIP_DEFLATED) as archive:
        for name, content in files.items():
            archive.writestr(name, content)
    return buffer.getvalue()


GEN = "\\id GEN World English Bible\n\\c 1\n\\p\n\\v 1 In the beginning God created the heavens and the earth.\n\\v 2 The earth was formless.\n"
JHN = "\\id JHN World English Bible\n\\c 3\n\\p\n\\v 16 For God so loved the world.\n\\v 17 For God did not send his Son to condemn the world.\n"


class FakeRequest:
    def __init__(self, payload: bytes):
        self.payload = payload
        self.headers = {"content-length": str(len(payload))}

    async def stream(self):
        middle = len(self.payload) // 2
        yield self.payload[:middle]
        yield self.payload[middle:]


class V22UsfmZipTests(unittest.TestCase):
    def test_multi_book_usfm_zip_converts_and_skips_readme(self):
        payload = make_zip({"01GENengwebp.SFM": GEN, "43JHNengwebp.SFM": JHN, "README.txt": "distribution notes"})
        items, files = convert_usfm_zip(payload)
        self.assertEqual(files, ["01GENengwebp.SFM", "43JHNengwebp.SFM"])
        self.assertEqual(len(items), 4)
        self.assertEqual(items[0]["reference"], "GEN 1:1")
        self.assertEqual(items[-1]["reference"], "JHN 3:17")

    def test_full_bible_style_66_file_archive_is_accepted(self):
        files = {
            f"{index:02d}BOOK.sfm": f"\\id B{index:02d}\n\\c 1\n\\v 1 Verse one for book {index}.\n\\v 2 Verse two for book {index}.\n"
            for index in range(1, 67)
        }
        items, converted = convert_usfm_zip(make_zip(files))
        self.assertEqual(len(converted), 66)
        self.assertEqual(len(items), 132)
        self.assertEqual(items[0]["reference"], "B01 1:1")
        self.assertEqual(items[-1]["reference"], "B66 1:2")

    def test_ebible_strong_attributes_do_not_leak_into_readable_text(self):
        source = '\\id GEN\n\\c 1\n\\v 1 In\\strong="H8064" the\\strong="H1254" beginning God created.\n'
        items, _ = convert_usfm_zip(make_zip({"01GENengwebp.SFM": source}))
        self.assertEqual(items[0]["text"], "In the beginning God created.")
        self.assertNotIn("strong", items[0]["text"])

    def test_standard_usfm_word_attributes_keep_only_visible_word(self):
        source = '\\id JHN\n\\c 1\n\\v 1 \\w Word|lemma="logos" strong="G3056"\\w* was here.\n'
        items, _ = convert_usfm_zip(make_zip({"43JHN.usfm": source}))
        self.assertEqual(items[0]["text"], "Word was here.")

    def test_readaloud_zip_gets_specific_guidance(self):
        payload = make_zip({"engwebp_000_000_000_read.txt": "title\tWorld English Bible\n", "engwebp_002_GEN_01_read.txt": "audio timing data"})
        with self.assertRaisesRegex(ValueError, "read-aloud.*engwebp_usfm.zip"):
            convert_usfm_zip(payload)

    def test_zip_path_traversal_is_rejected(self):
        payload = make_zip({"../evil.sfm": GEN})
        with self.assertRaisesRegex(ValueError, "안전하지 않은"):
            convert_usfm_zip(payload)

    def test_duplicate_reference_across_books_is_rejected(self):
        payload = make_zip({"a.sfm": GEN, "b.sfm": GEN})
        with self.assertRaisesRegex(ValueError, "중복 성경 참조"):
            convert_usfm_zip(payload)

    def test_suspicious_compression_ratio_is_rejected(self):
        payload = make_zip({"huge.txt": "0" * (1024 * 1024)})
        with self.assertRaisesRegex(ValueError, "압축률"):
            convert_usfm_zip(payload)

    def test_zip_api_streams_and_returns_file_count(self):
        payload = make_zip({"GEN.sfm": GEN, "JHN.usfm": JHN})
        result = asyncio.run(main.convert_bible_usfm_zip(FakeRequest(payload)))
        self.assertEqual(result["source_format"], "usfm_zip")
        self.assertEqual(result["file_count"], 2)
        self.assertEqual(result["count"], 4)

    def test_zip_api_rejects_invalid_archive(self):
        with self.assertRaises(HTTPException) as raised:
            asyncio.run(main.convert_bible_usfm_zip(FakeRequest(b"not-a-zip")))
        self.assertEqual(raised.exception.status_code, 400)
        self.assertIn("유효한 ZIP", raised.exception.detail)


if __name__ == "__main__":
    unittest.main()

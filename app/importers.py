from __future__ import annotations

import csv
import io
import json
import re
import zipfile
import xml.etree.ElementTree as ET
from pathlib import PurePosixPath

from app.references import expand_reference, normalize_reference, validate_primary_original_language


SUPPORTED_SOURCE_FORMATS = ("auto", "json", "csv", "tsv", "usfm", "osis", "sblgnt_xml")
MAX_CONVERT_ITEMS = 100_000
MAX_ZIP_UPLOAD_BYTES = 50 * 1024 * 1024
MAX_ZIP_UNCOMPRESSED_BYTES = 100 * 1024 * 1024
MAX_ZIP_ENTRIES = 500
MAX_ZIP_COMPRESSION_RATIO = 200
SUPPORTED_ORIGINAL_FORMATS = ("auto", "json", "csv", "tsv", "morphgnt", "oshb_osis")
MAX_ORIGINAL_IMPORT_ITEMS = 50_000
SUPPORTED_LEXICON_FORMATS = (
    "auto", "json", "csv", "tsv", "xml", "strongs_greek_xml", "hebrew_strongs_xml",
)
MAX_LEXICON_IMPORT_ITEMS = 100_000

_MORPHGNT_BOOKS = (
    "MAT", "MRK", "LUK", "JHN", "ACT", "ROM", "1CO", "2CO", "GAL", "EPH", "PHP", "COL",
    "1TH", "2TH", "1TI", "2TI", "TIT", "PHM", "HEB", "JAS", "1PE", "2PE", "1JN", "2JN",
    "3JN", "JUD", "REV",
)


def _clean(value: object) -> str:
    return str(value if value is not None else "").strip()


def _reference_from_mapping(item: dict) -> str:
    direct = _clean(item.get("reference"))
    if direct:
        return direct
    book = _clean(item.get("book"))
    chapter = _clean(item.get("chapter"))
    verse = _clean(item.get("verse"))
    return f"{book} {chapter}:{verse}" if book and chapter and verse else ""


def _text_from_mapping(item: dict) -> str:
    for key in ("text", "verse_text", "content"):
        value = _clean(item.get(key))
        if value:
            return value
    return ""


def _normalize(items: list[dict]) -> list[dict]:
    if not items:
        raise ValueError("변환할 성경 구절이 없습니다.")
    if len(items) > MAX_CONVERT_ITEMS:
        raise ValueError(f"한 번에 최대 {MAX_CONVERT_ITEMS:,}건까지 변환할 수 있습니다.")
    result: list[dict] = []
    seen: set[str] = set()
    for index, item in enumerate(items, 1):
        if not isinstance(item, dict):
            raise ValueError(f"{index}번째 항목이 객체 형식이 아닙니다.")
        reference = _reference_from_mapping(item)
        text = _text_from_mapping(item)
        if not reference or not text:
            raise ValueError(f"{index}번째 항목에 reference/text 또는 book/chapter/verse/text가 필요합니다.")
        key = reference.casefold()
        if key in seen:
            raise ValueError(f"중복 성경 참조가 있습니다: {reference}")
        seen.add(key)
        result.append({"reference": reference, "text": text})
    return result


def _json_items(content: str) -> list[dict]:
    data = json.loads(content.lstrip("\ufeff"))
    if isinstance(data, dict):
        for key in ("items", "verses", "data"):
            if isinstance(data.get(key), list):
                data = data[key]
                break
    if not isinstance(data, list):
        raise ValueError("JSON 최상위 값은 배열이거나 items/verses/data 배열을 포함한 객체여야 합니다.")
    return _normalize(data)


def _delimited_items(content: str, delimiter: str) -> list[dict]:
    stream = io.StringIO(content.lstrip("\ufeff"))
    reader = csv.DictReader(stream, delimiter=delimiter)
    if not reader.fieldnames:
        raise ValueError("CSV/TSV 헤더 행이 없습니다.")
    items: list[dict] = []
    for row in reader:
        lower = {str(key or "").strip().lower(): value for key, value in row.items()}
        items.append({
            "reference": lower.get("reference", ""),
            "book": lower.get("book", ""),
            "chapter": lower.get("chapter", ""),
            "verse": lower.get("verse", ""),
            "text": lower.get("text") or lower.get("verse_text") or lower.get("content") or "",
        })
    return _normalize(items)


_USFM_NOTE_RE = re.compile(r"\\(?:f|x)\s.*?\\(?:f|x)\*", re.IGNORECASE)
_USFM_WORD_RE = re.compile(r"\\\+?w\s+([^|\\]+?)(?:\|[^\\]*?)?\\\+?w\*", re.IGNORECASE)
_USFM_MARKER_RE = re.compile(r'\\[A-Za-z0-9+\-]+(?:="[^"]*")?\*?\s*')


def _clean_usfm_text(text: str) -> str:
    text = _USFM_NOTE_RE.sub(" ", text)
    # USFM \w 단어|속성 \w* 은 사람이 읽는 단어만 보존한다.
    text = _USFM_WORD_RE.sub(lambda match: match.group(1), text)
    # eBible WEB USFM의 단어 뒤 custom \strong="H..." 표식도 아래 marker 정리에서 제거된다.
    return re.sub(r"\s+", " ", _USFM_MARKER_RE.sub(" ", text)).strip()


def _usfm_items(content: str) -> list[dict]:
    book = ""
    chapter = ""
    current: dict | None = None
    items: list[dict] = []

    def flush() -> None:
        nonlocal current
        if current and current.get("text"):
            current["text"] = _clean_usfm_text(current["text"])
            if current["text"]:
                items.append(current)
        current = None

    for raw_line in content.lstrip("\ufeff").splitlines():
        line = raw_line.strip()
        if not line:
            continue
        if line.startswith("\\id "):
            flush()
            book = line[4:].strip().split()[0]
        elif line.startswith("\\c "):
            flush()
            chapter = line[3:].strip().split()[0]
        elif line.startswith("\\v "):
            flush()
            parts = line[3:].strip().split(maxsplit=1)
            if len(parts) < 2 or not book or not chapter:
                raise ValueError("USFM의 \\id, \\c, \\v 순서를 확인하세요.")
            current = {"reference": f"{book} {chapter}:{parts[0]}", "text": parts[1]}
        elif current:
            if line.startswith("\\"):
                marker_and_text = line.split(maxsplit=1)
                if len(marker_and_text) == 2 and marker_and_text[0].rstrip("*") in {"\\p", "\\m", "\\q", "\\q1", "\\q2", "\\mi"}:
                    current["text"] += " " + marker_and_text[1]
            else:
                current["text"] += " " + line
    flush()
    return _normalize(items)


def _osis_reference(osis_id: str) -> str:
    first = _clean(osis_id).split()[0] if _clean(osis_id) else ""
    parts = first.split(".")
    if len(parts) >= 3:
        return f"{parts[0]} {parts[1]}:{parts[2]}"
    return first


def _osis_items(content: str) -> list[dict]:
    try:
        root = ET.fromstring(content.lstrip("\ufeff"))
    except ET.ParseError as exc:
        raise ValueError(f"OSIS/XML 문법 오류: {exc}") from exc
    items: list[dict] = []
    for node in root.iter():
        if node.tag.rsplit("}", 1)[-1].lower() != "verse":
            continue
        reference = _osis_reference(node.attrib.get("osisID", "") or node.attrib.get("osisId", ""))
        text = re.sub(r"\s+", " ", "".join(node.itertext())).strip()
        if reference and text:
            items.append({"reference": reference, "text": text})
    if not items:
        root_name = root.tag.rsplit("}", 1)[-1].lower()
        names = {node.tag.rsplit("}", 1)[-1].lower() for node in list(root.iter())[:200]}
        if "lex" in root_name or any("lex" in name for name in names):
            raise ValueError(
                "선택한 XML은 성경 구절 본문이 아니라 어휘/색인 자료로 보입니다. "
                "SBLGNT 본문은 공식 data/sblgnt/xml 폴더의 Matt.xml 같은 책별 XML 또는 sblgnt.xml을 선택하세요."
            )
        raise ValueError("XML에서 <verse osisID=...> 형식의 성경 구절을 찾지 못했습니다.")
    return _normalize(items)


def _looks_like_sblgnt_xml(content: str) -> bool:
    probe = content.lstrip("\ufeff \t\r\n")[:20_000].lower()
    return "<verse-number" in probe and " id=" in probe


def _sblgnt_xml_items(content: str) -> list[dict]:
    """Convert the native Faithlife/SBLGNT XML (<verse-number id='Matthew 1:1'>)."""
    try:
        root = ET.fromstring(content.lstrip("\ufeff"))
    except ET.ParseError as exc:
        raise ValueError(f"SBLGNT XML 문법 오류: {exc}") from exc

    items: list[dict] = []
    current_reference = ""
    pieces: list[str] = []

    def flush() -> None:
        nonlocal current_reference, pieces
        if not current_reference:
            pieces = []
            return
        text = "".join(pieces)
        text = re.sub(r"[⸀-⸇]", "", text)
        text = re.sub(r"\s+", " ", text).strip()
        text = re.sub(r"\s+([.,;:·!?])", r"\1", text)
        if text:
            items.append({"reference": current_reference, "text": text})
        pieces = []

    for node in root.iter():
        name = node.tag.rsplit("}", 1)[-1].lower()
        if name == "verse-number":
            flush()
            raw_reference = _clean(node.attrib.get("id"))
            if not raw_reference:
                current_reference = ""
                continue
            try:
                current_reference = normalize_reference(raw_reference)
            except ValueError as exc:
                raise ValueError(f"SBLGNT verse-number 참조를 해석할 수 없습니다: {raw_reference}") from exc
        elif current_reference and name == "w":
            word = _clean("".join(node.itertext()))
            if word:
                pieces.append(word + " ")
        elif current_reference and name in {"prefix", "suffix"}:
            pieces.append("".join(node.itertext()))
    flush()
    if not items:
        raise ValueError(
            "SBLGNT XML에서 <verse-number id='Matthew 1:1'> 형식의 본문 구절을 찾지 못했습니다. "
            "LexicalIndex.xml이 아니라 Matt.xml 같은 책별 본문 XML 또는 sblgnt.xml을 선택하세요."
        )
    return _normalize(items)


def detect_source_format(content: str) -> str:
    stripped = content.lstrip("\ufeff \t\r\n")
    if stripped.startswith(("[", "{")):
        return "json"
    if stripped.startswith("<") and _looks_like_sblgnt_xml(content):
        return "sblgnt_xml"
    if stripped.startswith("<"):
        return "osis"
    if "\\id " in stripped[:2000] or "\\v " in stripped[:2000]:
        return "usfm"
    first_line = stripped.splitlines()[0] if stripped else ""
    if "\t" in first_line:
        return "tsv"
    if "," in first_line:
        return "csv"
    raise ValueError("파일 형식을 자동 감지하지 못했습니다. JSON/CSV/TSV/USFM/OSIS 중 하나를 직접 선택하세요.")


def convert_bible_source(content: str, source_format: str = "auto") -> tuple[str, list[dict]]:
    source_format = _clean(source_format).lower() or "auto"
    if source_format not in SUPPORTED_SOURCE_FORMATS:
        raise ValueError("지원하지 않는 성경 원본 형식입니다.")
    if not content.strip():
        raise ValueError("원본 파일 내용이 비어 있습니다.")
    resolved = detect_source_format(content) if source_format == "auto" else source_format
    # V35: 기존 화면에서 OSIS/XML을 직접 선택했더라도 공식 SBLGNT native XML은 정확히 재분류한다.
    if resolved == "osis" and _looks_like_sblgnt_xml(content):
        resolved = "sblgnt_xml"
    if resolved == "json":
        items = _json_items(content)
    elif resolved == "csv":
        items = _delimited_items(content, ",")
    elif resolved == "tsv":
        items = _delimited_items(content, "\t")
    elif resolved == "usfm":
        items = _usfm_items(content)
    elif resolved == "sblgnt_xml":
        items = _sblgnt_xml_items(content)
    else:
        items = _osis_items(content)
    return resolved, items


def convert_usfm_zip(data: bytes) -> tuple[list[dict], list[str]]:
    """Convert a multi-file USFM ZIP without extracting archive paths to disk."""
    if not data:
        raise ValueError("USFM ZIP 파일이 비어 있습니다.")
    if len(data) > MAX_ZIP_UPLOAD_BYTES:
        raise ValueError("USFM ZIP은 최대 50MB까지 변환할 수 있습니다.")
    buffer = io.BytesIO(data)
    if not zipfile.is_zipfile(buffer):
        raise ValueError("유효한 ZIP 파일이 아닙니다.")
    buffer.seek(0)
    items: list[dict] = []
    converted_files: list[str] = []
    archive_names: set[str] = set()
    total_uncompressed = 0
    readaloud_seen = False
    with zipfile.ZipFile(buffer, "r") as archive:
        infos = archive.infolist()
        if len(infos) > MAX_ZIP_ENTRIES:
            raise ValueError(f"ZIP 내부 파일이 {MAX_ZIP_ENTRIES}개를 초과합니다.")
        for info in infos:
            normalized_name = info.filename.replace("\\", "/")
            path = PurePosixPath(normalized_name)
            if path.is_absolute() or ".." in path.parts or normalized_name.startswith("/"):
                raise ValueError("ZIP에 안전하지 않은 파일 경로가 포함되어 있습니다.")
            key = normalized_name.casefold()
            if key in archive_names:
                raise ValueError(f"ZIP에 중복 파일명이 있습니다: {normalized_name}")
            archive_names.add(key)
            if info.flag_bits & 0x1:
                raise ValueError("암호화된 ZIP 파일은 변환할 수 없습니다.")
            total_uncompressed += info.file_size
            if total_uncompressed > MAX_ZIP_UNCOMPRESSED_BYTES:
                raise ValueError("ZIP 압축 해제 크기가 100MB 제한을 초과합니다.")
            if info.compress_size and info.file_size / info.compress_size > MAX_ZIP_COMPRESSION_RATIO:
                raise ValueError("비정상적으로 압축률이 높은 ZIP 항목이 있어 안전을 위해 중단했습니다.")
            if info.is_dir():
                continue
            suffix = path.suffix.lower()
            if suffix not in {".usfm", ".sfm", ".txt"}:
                continue
            if path.name.lower().endswith("_read.txt"):
                readaloud_seen = True
            raw = archive.read(info)
            try:
                content = raw.decode("utf-8-sig")
            except UnicodeDecodeError as exc:
                raise ValueError(f"UTF-8로 읽을 수 없는 USFM 파일입니다: {normalized_name}") from exc
            probe = content[:20_000]
            if "\\id " not in probe or "\\v " not in content:
                continue
            try:
                file_items = _usfm_items(content)
            except ValueError as exc:
                raise ValueError(f"{normalized_name} USFM 검사 실패: {exc}") from exc
            if len(items) + len(file_items) > MAX_CONVERT_ITEMS:
                raise ValueError(f"한 번에 최대 {MAX_CONVERT_ITEMS:,}건까지 변환할 수 있습니다.")
            items.extend(file_items)
            converted_files.append(normalized_name)
    if not items:
        if readaloud_seen:
            raise ValueError("read-aloud용 *_read.txt 파일은 성경 구절 USFM이 아닙니다. eBible의 engwebp_usfm.zip을 선택하세요.")
        raise ValueError("ZIP 안에서 \\id/\\c/\\v 구조의 USFM 성경 파일을 찾지 못했습니다.")
    return _normalize(items), converted_files


def _normalize_original_items(items: list[dict]) -> list[dict]:
    if not items:
        raise ValueError("변환할 원어 근거가 없습니다.")
    if len(items) > MAX_ORIGINAL_IMPORT_ITEMS:
        raise ValueError(f"원어 근거는 한 번에 최대 {MAX_ORIGINAL_IMPORT_ITEMS:,}건까지 변환할 수 있습니다.")
    result = []
    seen = set()
    for index, raw in enumerate(items, 1):
        if not isinstance(raw, dict):
            raise ValueError(f"{index}번째 원어 항목이 객체 형식이 아닙니다.")
        lowered = {str(key).strip().lower(): value for key, value in raw.items()}
        reference = _clean(lowered.get("reference") or lowered.get("ref"))
        language = _clean(lowered.get("language") or lowered.get("lang"))
        lemma = _clean(lowered.get("lemma"))
        if not reference or not language or not lemma:
            raise ValueError(f"{index}번째 항목에 reference, language, lemma가 필요합니다.")
        try:
            verses = expand_reference(reference)
            if len(verses) != 1:
                raise ValueError("범위 참조")
            reference = normalize_reference(reference)
        except ValueError as exc:
            raise ValueError(f"{index}번째 원어 근거의 reference는 한 절이어야 합니다: {reference}") from exc
        try:
            validate_primary_original_language(reference, language)
        except ValueError as exc:
            raise ValueError(f"{index}번째 원어 근거의 언어가 성경 구분과 맞지 않습니다: {exc}") from exc
        item = {
            "reference": reference,
            "language": language,
            "lemma": lemma,
            "transliteration": _clean(lowered.get("transliteration") or lowered.get("translit")),
            "gloss": _clean(lowered.get("gloss") or lowered.get("meaning")),
            "morphology": _clean(lowered.get("morphology") or lowered.get("morph")),
        }
        surface_form = _clean(lowered.get("surface_form") or lowered.get("surface") or lowered.get("text_form") or lowered.get("word_form"))
        if surface_form:
            item["surface_form"] = surface_form
        token_index = lowered.get("token_index") or lowered.get("position")
        if token_index not in (None, ""):
            try:
                item["token_index"] = int(token_index)
            except (TypeError, ValueError) as exc:
                raise ValueError(f"{index}번째 원어 항목의 token_index가 올바르지 않습니다.") from exc
        # Native tokenized sources may legitimately repeat the same lemma and
        # morphology in one verse; token_index keeps those occurrences distinct.
        occurrence = item.get("token_index") if surface_form else None
        key = (reference, language.casefold(), lemma.casefold(), item["morphology"].casefold(), occurrence)
        if key in seen:
            raise ValueError(f"중복 원어 근거가 있습니다: {reference} · {lemma}")
        seen.add(key)
        result.append(item)
    return result


def _dedupe_native_original_items(items: list[dict]) -> list[dict]:
    """Collapse repeated occurrences that carry the same lemma + morphology in one verse."""
    result = []
    seen = set()
    for item in items:
        key = (
            _clean(item.get("reference")), _clean(item.get("language")).casefold(),
            _clean(item.get("lemma")).casefold(), _clean(item.get("morphology")).casefold(),
        )
        if key in seen:
            continue
        seen.add(key)
        result.append(item)
    return result


def _morphgnt_original_items(content: str) -> list[dict]:
    items = []
    token_indexes = {}
    for line_no, raw in enumerate(content.lstrip("\ufeff").splitlines(), 1):
        line = raw.strip()
        if not line:
            continue
        fields = line.split()
        if len(fields) < 7 or not re.fullmatch(r"\d{6}", fields[0]):
            raise ValueError(f"MorphGNT {line_no}번째 줄 형식이 올바르지 않습니다.")
        code, part_of_speech, parsing_code = fields[:3]
        book_no, chapter, verse = int(code[:2]), int(code[2:4]), int(code[4:6])
        if not 1 <= book_no <= len(_MORPHGNT_BOOKS) or chapter < 1 or verse < 1:
            raise ValueError(f"MorphGNT {line_no}번째 줄의 책/장/절 코드가 올바르지 않습니다: {code}")
        reference = f"{_MORPHGNT_BOOKS[book_no - 1]} {chapter}:{verse}"
        token_indexes[reference] = token_indexes.get(reference, 0) + 1
        items.append({
            "reference": reference,
            "language": "grc",
            "lemma": fields[-1],
            "transliteration": "",
            "gloss": "",
            "morphology": f"{part_of_speech} {parsing_code}",
            "surface_form": fields[3],
            "token_index": token_indexes[reference],
        })
    return _dedupe_native_original_items(items)


def _oshb_osis_original_items(content: str) -> list[dict]:
    try:
        root = ET.fromstring(content.lstrip("\ufeff"))
    except ET.ParseError as exc:
        raise ValueError(f"OSHB OSIS/XML 문법 오류: {exc}") from exc
    items = []
    for verse in root.iter():
        if verse.tag.rsplit("}", 1)[-1] != "verse":
            continue
        osis_id = _clean(verse.attrib.get("osisID"))
        parts = osis_id.split(".")
        if len(parts) < 3 or not parts[1].isdigit() or not parts[2].isdigit():
            continue
        reference = f"{parts[0]} {parts[1]}:{parts[2]}"
        token_index = 0
        for word in verse.iter():
            if word.tag.rsplit("}", 1)[-1] != "w":
                continue
            lemma = _clean(word.attrib.get("lemma"))
            if not lemma:
                continue
            morph = _clean(word.attrib.get("morph"))
            token_index += 1
            # OSHB morphology uses A for Biblical Aramaic and H for Hebrew when present.
            language = "arc" if morph.startswith("A") else "he"
            items.append({
                "reference": reference,
                "language": language,
                "lemma": lemma,
                "transliteration": "",
                "gloss": "",
                "morphology": morph,
                "surface_form": "".join(word.itertext()).strip(),
                "token_index": token_index,
            })
    if not items:
        raise ValueError("OSHB OSIS/XML에서 lemma가 있는 <w> 단어를 찾지 못했습니다.")
    return items


def iter_oshb_zip_original_files(data: bytes):
    """Yield (archive path, normalized items) for OSHB wlc/*.xml after ZIP safety checks."""
    if not data:
        raise ValueError("OSHB ZIP 파일이 비어 있습니다.")
    if len(data) > MAX_ZIP_UPLOAD_BYTES:
        raise ValueError("OSHB ZIP은 최대 50MB까지 처리할 수 있습니다.")
    buffer = io.BytesIO(data)
    if not zipfile.is_zipfile(buffer):
        raise ValueError("유효한 OSHB ZIP 파일이 아닙니다.")
    buffer.seek(0)
    with zipfile.ZipFile(buffer, "r") as archive:
        infos = archive.infolist()
        if len(infos) > MAX_ZIP_ENTRIES:
            raise ValueError(f"OSHB ZIP 내부 파일이 {MAX_ZIP_ENTRIES}개를 초과합니다.")
        names = set()
        total_uncompressed = 0
        candidates = []
        for info in infos:
            normalized_name = info.filename.replace("\\", "/")
            path = PurePosixPath(normalized_name)
            if path.is_absolute() or ".." in path.parts or normalized_name.startswith("/"):
                raise ValueError("OSHB ZIP에 안전하지 않은 파일 경로가 포함되어 있습니다.")
            key = normalized_name.casefold()
            if key in names:
                raise ValueError(f"OSHB ZIP에 중복 파일명이 있습니다: {normalized_name}")
            names.add(key)
            if info.flag_bits & 0x1:
                raise ValueError("암호화된 OSHB ZIP은 처리할 수 없습니다.")
            total_uncompressed += info.file_size
            if total_uncompressed > MAX_ZIP_UNCOMPRESSED_BYTES:
                raise ValueError("OSHB ZIP 압축 해제 크기가 100MB 제한을 초과합니다.")
            if info.compress_size and info.file_size / info.compress_size > MAX_ZIP_COMPRESSION_RATIO:
                raise ValueError("비정상적으로 압축률이 높은 OSHB ZIP 항목이 있어 중단했습니다.")
            parts_lower = {part.casefold() for part in path.parts}
            filename_lower = path.name.casefold()
            official_root_layout = (
                len(path.parts) == 2
                and path.parts[0].casefold().startswith("oshb-v.")
                and filename_lower != "VerseMap.xml".casefold()
                and not path.parts[0].casefold().startswith("__macosx")
            )
            if not info.is_dir() and path.suffix.lower() == ".xml" and ("wlc" in parts_lower or official_root_layout):
                candidates.append(info)
        if not candidates:
            raise ValueError("OSHB ZIP에서 wlc/*.xml 성경책 파일을 찾지 못했습니다. 공식 MorphHB/OSHB 배포 ZIP인지 확인하세요.")
        for info in candidates:
            raw = archive.read(info)
            try:
                content = raw.decode("utf-8-sig")
            except UnicodeDecodeError as exc:
                raise ValueError(f"OSHB XML UTF-8 해석 실패: {info.filename}") from exc
            items = _normalize_original_items(_oshb_osis_original_items(content))
            yield info.filename.replace("\\", "/"), items


def convert_original_note_source(content: str, source_format: str = "auto") -> tuple[str, list[dict]]:
    source_format = _clean(source_format).lower() or "auto"
    if source_format not in SUPPORTED_ORIGINAL_FORMATS:
        raise ValueError("지원하지 않는 원어 근거 파일 형식입니다.")
    if not content.strip():
        raise ValueError("원어 근거 파일 내용이 비어 있습니다.")
    stripped = content.lstrip("\ufeff \t\r\n")
    if source_format == "auto":
        if stripped.startswith(("[", "{")):
            source_format = "json"
        elif stripped.startswith("<") and ("osis" in stripped[:2000].lower() or "osisid=" in stripped[:5000].lower()):
            source_format = "oshb_osis"
        else:
            first = stripped.splitlines()[0] if stripped else ""
            source_format = "morphgnt" if re.match(r"^\d{6}\s+\S+\s+\S+\s+", first) else "tsv" if "\t" in first else "csv" if "," in first else ""
        if not source_format:
            raise ValueError("원어 근거 형식을 자동 감지하지 못했습니다. JSON/CSV/TSV/MorphGNT/OSHB OSIS 중 하나를 선택하세요.")
    if source_format == "json":
        data = json.loads(content.lstrip("\ufeff"))
        if isinstance(data, dict):
            for key in ("items", "words", "data"):
                if isinstance(data.get(key), list):
                    data = data[key]
                    break
        if not isinstance(data, list):
            raise ValueError("원어 JSON은 배열 또는 items/words/data 배열을 포함해야 합니다.")
        items = data
    elif source_format in {"csv", "tsv"}:
        reader = csv.DictReader(io.StringIO(content.lstrip("\ufeff")), delimiter="\t" if source_format == "tsv" else ",")
        if not reader.fieldnames:
            raise ValueError("원어 CSV/TSV 헤더가 없습니다.")
        items = list(reader)
    elif source_format == "morphgnt":
        items = _morphgnt_original_items(content)
    else:
        items = _oshb_osis_original_items(content)
    return source_format, _normalize_original_items(items)


def _normalize_lexicon_items(items: list[dict]) -> list[dict]:
    if not items:
        raise ValueError("변환할 원어 사전 항목이 없습니다.")
    if len(items) > MAX_LEXICON_IMPORT_ITEMS:
        raise ValueError(f"원어 사전은 한 번에 최대 {MAX_LEXICON_IMPORT_ITEMS:,}건까지 검사할 수 있습니다.")
    result = []
    seen = set()
    for index, raw in enumerate(items, 1):
        if not isinstance(raw, dict):
            raise ValueError(f"{index}번째 원어 사전 항목이 객체 형식이 아닙니다.")
        lowered = {str(key).strip().lower(): value for key, value in raw.items()}
        language = _clean(lowered.get("language") or lowered.get("lang")).casefold()
        lemma = _clean(lowered.get("lemma") or lowered.get("headword"))
        gloss = _clean(lowered.get("gloss") or lowered.get("meaning"))
        transliteration = _clean(lowered.get("transliteration") or lowered.get("translit"))
        if not language or not lemma or not gloss:
            raise ValueError(f"{index}번째 원어 사전에 language, lemma, gloss가 필요합니다.")
        if len(language) > 20 or len(lemma) > 200 or len(transliteration) > 200 or len(gloss) > 5000:
            raise ValueError(f"{index}번째 원어 사전 항목이 허용 길이를 초과했습니다.")
        key = (language, lemma.casefold())
        if key in seen:
            raise ValueError(f"중복 원어 사전 항목이 있습니다: {language} · {lemma}")
        seen.add(key)
        result.append({"language": language, "lemma": lemma, "transliteration": transliteration, "gloss": gloss})
    return result


def _xml_text(element: ET.Element | None) -> str:
    """Return readable text from a lexicon XML element, including nested tags."""
    if element is None:
        return ""
    return re.sub(r"\s+", " ", "".join(element.itertext())).strip(" :;-\t\r\n")


def _strongs_greek_lexicon_items(content: str) -> list[dict]:
    try:
        root = ET.fromstring(content.lstrip("\ufeff"))
    except ET.ParseError as exc:
        raise ValueError(f"Strong 헬라어 XML 문법 오류: {exc}") from exc
    items = []
    for entry in root.iter("entry"):
        greek = entry.find("greek")
        if greek is None:
            continue
        lemma = _clean(greek.attrib.get("unicode"))
        gloss = _xml_text(entry.find("strongs_def")) or _xml_text(entry.find("kjv_def"))
        if lemma and gloss:
            items.append({
                "language": "grc", "lemma": lemma,
                "transliteration": _clean(greek.attrib.get("translit")), "gloss": gloss,
            })
    if not items:
        raise ValueError("Strong 헬라어 XML에서 greek unicode와 strongs_def 항목을 찾지 못했습니다.")
    return items


def _hebrew_strongs_lexicon_items(content: str) -> list[dict]:
    try:
        root = ET.fromstring(content.lstrip("\ufeff"))
    except ET.ParseError as exc:
        raise ValueError(f"Strong 히브리어 XML 문법 오류: {exc}") from exc
    items = []
    for entry in root.iter():
        if entry.tag.rsplit("}", 1)[-1] != "entry":
            continue
        strong_id = _clean(entry.attrib.get("id"))
        word = next((node for node in entry if node.tag.rsplit("}", 1)[-1] == "w"), None)
        if not strong_id or word is None:
            continue
        children = {node.tag.rsplit("}", 1)[-1]: node for node in entry}
        gloss = _xml_text(children.get("meaning")) or _xml_text(children.get("usage"))
        xml_lang = _clean(word.attrib.get("{http://www.w3.org/XML/1998/namespace}lang")).casefold()
        if gloss:
            items.append({
                "language": "arc" if xml_lang == "arc" else "he",
                # OSHB 원문은 Strong 계열 숫자를 lemma로 사용하므로 entry id가 연결 키입니다.
                "lemma": strong_id, "transliteration": _clean(word.attrib.get("xlit")),
                "gloss": gloss,
            })
    if not items:
        raise ValueError("Strong 히브리어 XML에서 entry id, w, meaning/usage 항목을 찾지 못했습니다.")
    return items


def classify_original_language_source(content: str, filename: str = "") -> str:
    """Classify original-language uploads by role before choosing a converter."""
    stripped = content.lstrip("\ufeff \t\r\n")
    if not stripped:
        return "unknown"
    safe_name = PurePosixPath(str(filename or "").replace("\\", "/")).name.casefold()
    # The well-known official filenames are strong hints. The selected converter still
    # validates the XML structure before any database write.
    if safe_name == "strongsgreek.xml":
        return "strongs_greek_lexicon"
    if safe_name == "hebrewstrong.xml":
        return "hebrew_strongs_lexicon"
    if safe_name.endswith("-morphgnt.txt"):
        return "morphgnt_original"
    first = stripped.splitlines()[0] if stripped else ""
    if re.match(r"^\d{6}\s+\S+\s+\S+\s+", first):
        return "morphgnt_original"
    lower = stripped[:131072].lower()
    # SBLGNT의 Matt.xml, 1Cor.xml, sblgnt.xml은 lemma/형태론 표가 아니라
    # 헬라어 성경 본문이다. 간편 등록에서 passages DB로 보내기 위해 별도
    # 역할로 분류한다. 파일명이 아니라 verse-number 구조로 최종 판별한다.
    if stripped.startswith("<") and _looks_like_sblgnt_xml(content):
        return "sblgnt_bible"
    if stripped.startswith("<") and "strongsdictionary" in lower and "<greek" in lower:
        return "strongs_greek_lexicon"
    if stripped.startswith("<") and "<lexicon" in lower and "<entry" in lower and "morphhb/namespace" in lower:
        return "hebrew_strongs_lexicon"
    if stripped.startswith("<") and ("osis" in lower or "osisid=" in lower):
        return "oshb_original"
    if stripped.startswith(("[", "{")):
        return "structured_candidate"
    header = [part.strip().lower() for part in re.split(r"[\t,]", first)]
    if {"language", "lemma", "gloss"}.issubset(header):
        return "lexicon"
    if {"reference", "language", "lemma"}.issubset(header):
        return "original_notes"
    return "unknown"


def convert_lexicon_source(content: str, source_format: str = "auto") -> tuple[str, list[dict]]:
    source_format = _clean(source_format).lower() or "auto"
    if source_format not in SUPPORTED_LEXICON_FORMATS:
        raise ValueError("지원하지 않는 원어 사전 파일 형식입니다.")
    if not content.strip():
        raise ValueError("원어 사전 파일 내용이 비어 있습니다.")
    stripped = content.lstrip("\ufeff \t\r\n")
    role = classify_original_language_source(content)
    if role == "morphgnt_original":
        raise ValueError(
            "선택한 파일은 원어 뜻 사전이 아니라 MorphGNT 형태론·lemma 원문 자료입니다. "
            "위 '원어 근거 파일 일괄 가져오기'에서 MorphGNT 형식으로 등록하세요. "
            "61-Mt-morphgnt.txt는 마태복음 원어 근거 파일입니다."
        )
    if role == "oshb_original":
        raise ValueError(
            "선택한 XML은 원어 뜻 사전이 아니라 OSHB 원문 형태론 자료입니다. "
            "위 '원어 근거 파일 일괄 가져오기'에서 OSHB · OSIS/XML로 등록하세요."
        )
    if source_format in {"auto", "xml"}:
        if stripped.startswith("<"):
            if role == "strongs_greek_lexicon":
                source_format = "strongs_greek_xml"
            elif role == "hebrew_strongs_lexicon":
                source_format = "hebrew_strongs_xml"
            else:
                raise ValueError(
                    "지원하는 사전 XML이 아닙니다. Strong 헬라어 strongsgreek.xml 또는 "
                    "Open Scriptures HebrewStrong.xml을 선택하세요. OSHB 책별 OSIS/XML은 "
                    "위 '원어 근거 파일 일괄 가져오기'에 등록해야 합니다."
                )
        elif stripped.startswith(("[", "{")):
            source_format = "json"
        else:
            first = stripped.splitlines()[0] if stripped else ""
            source_format = "tsv" if "\t" in first else "csv" if "," in first else ""
        if not source_format:
            raise ValueError("원어 사전 형식을 자동 감지하지 못했습니다. JSON/CSV/TSV 중 하나를 선택하세요.")
    if source_format == "strongs_greek_xml":
        items = _strongs_greek_lexicon_items(content)
    elif source_format == "hebrew_strongs_xml":
        items = _hebrew_strongs_lexicon_items(content)
    elif source_format == "json":
        data = json.loads(content.lstrip("\ufeff"))
        if isinstance(data, dict):
            for key in ("items", "entries", "words", "data"):
                if isinstance(data.get(key), list):
                    data = data[key]
                    break
        if not isinstance(data, list):
            raise ValueError("원어 사전 JSON은 배열 또는 items/entries/words/data 배열을 포함해야 합니다.")
        items = data
    else:
        reader = csv.DictReader(io.StringIO(content.lstrip("\ufeff")), delimiter="\t" if source_format == "tsv" else ",")
        if not reader.fieldnames:
            raise ValueError("원어 사전 CSV/TSV 헤더가 없습니다.")
        items = list(reader)
    return source_format, _normalize_lexicon_items(items)

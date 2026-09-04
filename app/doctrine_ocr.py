"""Explicit OCR boundary for scanned doctrine sources.

OCR is opt-in. The Tesseract adapter is deliberately limited to image input;
PDF rasterisation remains a separate, explicit boundary.
"""

from __future__ import annotations

from dataclasses import dataclass
import os
from pathlib import Path
import subprocess
import tempfile
from typing import Protocol


class OcrUnavailable(RuntimeError):
    pass


@dataclass(frozen=True)
class OcrResult:
    text: str
    confidence: float
    page_count: int
    provider: str


@dataclass(frozen=True)
class OcrReadiness:
    available: bool
    command: str
    version: str | None
    languages: tuple[str, ...]
    missing_languages: tuple[str, ...]
    message: str


class DoctrineOcrProvider(Protocol):
    def extract(self, content: bytes, mime_type: str = "application/pdf") -> OcrResult: ...


def ocr_min_confidence(environ: dict[str, str] | None = None) -> float:
    env = os.environ if environ is None else environ
    raw = env.get("DOCTRINE_OCR_MIN_CONFIDENCE", "0.85")
    try:
        value = float(raw)
    except (TypeError, ValueError) as exc:
        raise ValueError("DOCTRINE_OCR_MIN_CONFIDENCE는 0과 1 사이의 숫자여야 합니다.") from exc
    if not 0 <= value <= 1:
        raise ValueError("DOCTRINE_OCR_MIN_CONFIDENCE는 0과 1 사이여야 합니다.")
    return value


class DisabledOcrProvider:
    def extract(self, content: bytes, mime_type: str = "application/pdf") -> OcrResult:
        raise OcrUnavailable("OCR provider가 비활성화되어 스캔 문서는 검토 대기 상태입니다.")


def check_tesseract_readiness(command: str | None = None,
                              required_languages: tuple[str, ...] = ("heb", "grc")) -> OcrReadiness:
    """Check an explicitly configured Tesseract binary without installing anything."""
    executable = command or os.environ.get("DOCTRINE_TESSERACT_CMD", "tesseract")
    try:
        version_result = subprocess.run(
            [executable, "--version"], check=False, capture_output=True,
            timeout=10, shell=False,
        )
        if version_result.returncode != 0:
            raise OcrUnavailable("Tesseract 버전 확인에 실패했습니다.")
        version = version_result.stdout.decode("utf-8", errors="replace").splitlines()[0].strip()
        languages_result = subprocess.run(
            [executable, "--list-langs"], check=False, capture_output=True,
            timeout=10, shell=False,
        )
        if languages_result.returncode != 0:
            raise OcrUnavailable("Tesseract 언어 목록 확인에 실패했습니다.")
        languages = tuple(
            line.strip() for line in languages_result.stdout.decode("utf-8", errors="replace").splitlines()
            if line.strip() and not line.lower().startswith("list of available")
        )
    except (FileNotFoundError, OSError):
        return OcrReadiness(False, executable, None, (), tuple(required_languages),
                            "Tesseract 실행파일이 준비되지 않았습니다.")
    except subprocess.TimeoutExpired:
        return OcrReadiness(False, executable, None, (), tuple(required_languages),
                            "Tesseract readiness 확인 시간이 제한을 초과했습니다.")
    except OcrUnavailable as exc:
        return OcrReadiness(False, executable, None, (), tuple(required_languages), str(exc))
    missing = tuple(language for language in required_languages if language not in languages)
    if missing:
        return OcrReadiness(False, executable, version, languages, missing,
                            f"필수 OCR 언어 데이터가 없습니다: {', '.join(missing)}")
    return OcrReadiness(True, executable, version, languages, (), "Tesseract와 필수 언어 데이터가 준비되었습니다.")


class TesseractOcrProvider:
    """Run a pre-installed Tesseract binary against one image.

    The executable is never downloaded and shell execution is disabled. PDF
    input is rejected because rasterisation needs its own reviewed dependency
    and resource limits.
    """

    _IMAGE_MIME_TYPES = {"image/png", "image/jpeg", "image/tiff", "image/bmp", "image/webp"}

    def __init__(self, command: str | None = None, languages: str | None = None,
                 timeout_seconds: int | None = None, page_segmentation_mode: int | None = None,
                 tessdata_dir: str | None = None):
        self.command = command or os.environ.get("DOCTRINE_TESSERACT_CMD", "tesseract")
        self.languages = languages or os.environ.get("DOCTRINE_OCR_LANGS", "heb+grc+eng")
        raw_timeout = timeout_seconds if timeout_seconds is not None else os.environ.get(
            "DOCTRINE_OCR_TIMEOUT_SECONDS", "120"
        )
        try:
            self.timeout_seconds = int(raw_timeout)
        except (TypeError, ValueError) as exc:
            raise ValueError("DOCTRINE_OCR_TIMEOUT_SECONDS는 정수여야 합니다.") from exc
        if self.timeout_seconds < 1:
            raise ValueError("DOCTRINE_OCR_TIMEOUT_SECONDS는 1 이상이어야 합니다.")
        if not self.languages or any(ch.isspace() for ch in self.languages):
            raise ValueError("DOCTRINE_OCR_LANGS는 공백 없는 Tesseract 언어 목록이어야 합니다.")
        raw_psm = page_segmentation_mode if page_segmentation_mode is not None else os.environ.get(
            "DOCTRINE_OCR_PSM", "6"
        )
        try:
            self.page_segmentation_mode = int(raw_psm)
        except (TypeError, ValueError) as exc:
            raise ValueError("DOCTRINE_OCR_PSM은 정수여야 합니다.") from exc
        if not 3 <= self.page_segmentation_mode <= 13:
            raise ValueError("DOCTRINE_OCR_PSM은 3부터 13 사이여야 합니다.")
        self.tessdata_dir = tessdata_dir or os.environ.get("DOCTRINE_TESSDATA_DIR")

    def extract(self, content: bytes, mime_type: str = "application/pdf") -> OcrResult:
        if mime_type not in self._IMAGE_MIME_TYPES:
            raise OcrUnavailable("Tesseract OCR 어댑터는 이미지 입력만 지원하며 PDF는 렌더링 검토가 필요합니다.")
        if not content:
            raise ValueError("OCR 입력 이미지가 비어 있습니다.")

        suffix = "." + mime_type.split("/", 1)[1].replace("jpeg", "jpg")
        with tempfile.TemporaryDirectory(prefix="doctrine-ocr-") as temp_dir:
            input_path = Path(temp_dir) / ("input" + suffix)
            input_path.write_bytes(content)
            command = [self.command, str(input_path), "stdout", "--psm", str(self.page_segmentation_mode)]
            if self.tessdata_dir:
                command.extend(["--tessdata-dir", self.tessdata_dir])
            command.extend(["-l", self.languages, "tsv"])
            try:
                completed = subprocess.run(
                    command,
                    check=False,
                    capture_output=True,
                    timeout=self.timeout_seconds,
                    shell=False,
                )
            except (FileNotFoundError, OSError) as exc:
                raise OcrUnavailable("Tesseract 실행파일을 찾을 수 없습니다.") from exc
            except subprocess.TimeoutExpired as exc:
                raise OcrUnavailable("Tesseract OCR 시간이 제한을 초과했습니다.") from exc
            if completed.returncode != 0:
                detail = completed.stderr.decode("utf-8", errors="replace").strip()
                raise OcrUnavailable(f"Tesseract OCR이 실패했습니다{': ' + detail if detail else ''}")
            text, confidence = self._parse_tsv(completed.stdout)
            return OcrResult(text=text, confidence=confidence, page_count=1, provider="tesseract")

    @staticmethod
    def _parse_tsv(raw: bytes) -> tuple[str, float]:
        lines = raw.decode("utf-8", errors="replace").splitlines()
        words: list[str] = []
        confidences: list[float] = []
        for line in lines[1:]:
            columns = line.split("\t")
            if len(columns) < 12:
                continue
            word = columns[11].strip()
            if not word:
                continue
            try:
                confidence = float(columns[10])
            except ValueError:
                continue
            if confidence >= 0:
                words.append(word)
                confidences.append(confidence)
        if not words:
            return "", 0.0
        return " ".join(words), sum(confidences) / len(confidences) / 100


def validate_ocr_result(result: OcrResult, minimum_confidence: float | None = None) -> None:
    threshold = ocr_min_confidence() if minimum_confidence is None else minimum_confidence
    if not result.text.strip():
        raise ValueError("OCR 결과 본문이 비어 있습니다.")
    if not 0 <= result.confidence <= 1:
        raise ValueError("OCR confidence는 0과 1 사이여야 합니다.")
    if result.confidence < threshold:
        raise ValueError(f"OCR confidence {result.confidence:.3f}가 기준 {threshold:.3f}보다 낮습니다.")
    if result.page_count < 1:
        raise ValueError("OCR 페이지 수가 유효하지 않습니다.")

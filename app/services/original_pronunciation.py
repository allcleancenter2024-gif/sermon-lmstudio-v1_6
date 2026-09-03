"""Conservative, source-traceable pronunciation helpers for original-language words.

These are reading aids for sermon preparation, not a replacement for a trained
reader or a phonetic transcription.  The source surface form is always kept.
"""

import unicodedata


_HEBREW = {
    "א": "ʾ", "ב": "b", "ג": "g", "ד": "d", "ה": "h", "ו": "w", "ז": "z",
    "ח": "ḥ", "ט": "ṭ", "י": "y", "כ": "k", "ך": "k", "ל": "l", "מ": "m",
    "ם": "m", "נ": "n", "ן": "n", "ס": "s", "ע": "ʿ", "פ": "p", "ף": "p",
    "צ": "ṣ", "ץ": "ṣ", "ק": "q", "ר": "r", "ש": "š", "ת": "t",
}
_HEBREW_VOWELS = {"ַ": "a", "ָ": "ā", "ֶ": "e", "ֵ": "ē", "ִ": "i", "ֹ": "ō", "ֻ": "u", "ְ": "ə", "ֲ": "ă", "ֱ": "ĕ", "ֳ": "ŏ"}
_GREEK = {"α": "a", "β": "b", "γ": "g", "δ": "d", "ε": "e", "ζ": "z", "η": "ē", "θ": "th", "ι": "i", "κ": "k", "λ": "l", "μ": "m", "ν": "n", "ξ": "x", "ο": "o", "π": "p", "ρ": "r", "σ": "s", "ς": "s", "τ": "t", "υ": "y", "φ": "ph", "χ": "ch", "ψ": "ps", "ω": "ō"}


def pronunciation(surface_form: str, language: str) -> str:
    """Return a reproducible academic reading aid with Unicode diacritics."""
    text = unicodedata.normalize("NFC", str(surface_form or "")).strip()
    if language.casefold() in {"he", "arc"}:
        result = []
        for char in text:
            result.append(_HEBREW.get(char, _HEBREW_VOWELS.get(char, char if not unicodedata.combining(char) else "")))
        return "".join(result)
    if language.casefold() == "grc":
        return "".join(_GREEK.get(char.casefold(), char) for char in text)
    return ""


def pronunciation_scheme(language: str) -> str:
    return "학술식 로마자 독음 안내(참고)" if language.casefold() in {"he", "arc", "grc"} else ""

"""CLI for non-destructive SBLGNT corpus validation."""

from app.corpus_validator import validate_sblgnt_corpus
from app.paths import DATA_DIR


if __name__ == "__main__":
    report = validate_sblgnt_corpus(output_path=DATA_DIR / "bible" / "greek" / "derived" / "sblgnt_corpus_validation.json")
    print({"ok": report["ok"], "books": report["books_found"], "verses": report["total_verses"], "issues": len(report["issues"]), "output_path": report["output_path"]})

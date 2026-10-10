"""Schema validation for an operator-supplied reference-source fixture.

The validator does not promote a source to ``verified`` and does not persist
the fixture.  It only checks that the review evidence fields are present.
"""

from __future__ import annotations

from typing import Any


REQUIRED_FIELDS = frozenset({"id", "label", "category", "url", "citation", "license_note", "verification_status"})


def validate_reference_fixture(payload: Any) -> list[str]:
    """Return schema errors for a JSON-like source fixture."""
    errors: list[str] = []
    if not isinstance(payload, list) or not payload:
        return ["fixture must be a non-empty list"]
    ids: set[str] = set()
    for index, item in enumerate(payload):
        prefix = f"item[{index}]"
        if not isinstance(item, dict):
            errors.append(f"{prefix} must be an object")
            continue
        missing = sorted(field for field in REQUIRED_FIELDS if not str(item.get(field) or "").strip())
        errors.extend(f"{prefix}: {field} is required" for field in missing)
        source_id = str(item.get("id") or "").strip()
        if source_id and source_id in ids:
            errors.append(f"{prefix}: duplicate id {source_id}")
        if source_id:
            ids.add(source_id)
        status = str(item.get("verification_status") or "").strip()
        if status == "verified":
            for field in ("approval_ref", "reviewed_by", "reviewed_at"):
                if not str(item.get(field) or "").strip():
                    errors.append(f"{prefix}: verified source requires {field}")
        if bool(item.get("allowed_for_application")) and status != "verified":
            errors.append(f"{prefix}: application requires verified status")
    return errors


__all__ = ["REQUIRED_FIELDS", "validate_reference_fixture"]

"""Application boundary for grounded sermon generation.

The existing sermon service remains the implementation.  This facade keeps
the main application entry point independent from service module paths while
preserving model selection, no-thinking enforcement, duration correction,
grounding audit, and generation cancellation behavior.
"""

from app.services import sermon_service
from app.application.profiles import select_request_profiles


def generate_sermon_workflow(*args, **kwargs):
    data = args[0] if args else kwargs.get("data")
    selection = select_request_profiles(data) if data is not None else None
    result = sermon_service.generate_sermon_workflow(*args, **kwargs)
    if selection is not None and isinstance(result, dict):
        result["profiles"] = {
            "denomination": selection.denomination.code,
            "audience": selection.audience.code,
            "sermon_format": selection.sermon_format.code,
            "warnings": list(selection.warnings),
        }
    return result

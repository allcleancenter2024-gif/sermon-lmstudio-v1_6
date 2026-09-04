"""Application boundary for grounded sermon generation.

The existing sermon service remains the implementation.  This facade keeps
the main application entry point independent from service module paths while
preserving model selection, no-thinking enforcement, duration correction,
grounding audit, and generation cancellation behavior.
"""

from app.services import sermon_service


def generate_sermon_workflow(*args, **kwargs):
    return sermon_service.generate_sermon_workflow(*args, **kwargs)

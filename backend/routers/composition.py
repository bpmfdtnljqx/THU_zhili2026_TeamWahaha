"""
Composition router (placeholder).

POST /composition — reserved for the future AI Composition module.
Returns HTTP 501 Not Implemented until the module is built.
"""

from fastapi import APIRouter
from fastapi.responses import JSONResponse

from backend.models import CompositionRequest

router = APIRouter(tags=["composition"])


@router.post("/composition")
def compose(request: CompositionRequest):
    """Generate original music from a prompt. NOT YET IMPLEMENTED.

    Future integration point for the Composition module.
    When implemented:
      1. Import the composer (e.g. ``from composition import Composer``)
      2. Call it with request.prompt, request.style, and request.duration_s
      3. Return the standard response envelope with module="composition"

    See docs/API_SPEC.md §Composition for the planned schema.
    """
    return JSONResponse(
        status_code=501,
        content={
            "success": False,
            "module": "composition",
            "error": (
                "AI Composition is not yet implemented. "
                "This endpoint is reserved for future integration."
            ),
        },
    )

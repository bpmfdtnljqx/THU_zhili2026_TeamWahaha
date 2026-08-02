"""
Recognition router (placeholder).

POST /recognition — reserved for the future Music Recognition module.
Returns HTTP 501 Not Implemented until the module is built.
"""

from fastapi import APIRouter
from fastapi.responses import JSONResponse

from backend.models import RecognitionRequest

router = APIRouter(tags=["recognition"])


@router.post("/recognition")
def recognize(request: RecognitionRequest):
    """Identify a song from audio input. NOT YET IMPLEMENTED.

    Future integration point for the Recognition module.
    When implemented:
      1. Import the recognizer (e.g. ``from recognition import Recognizer``)
      2. Call it with request.audio and request.sample_rate
      3. Return the standard response envelope with module="recognition"

    See docs/API_SPEC.md §Recognition for the planned schema.
    """
    return JSONResponse(
        status_code=501,
        content={
            "success": False,
            "module": "recognition",
            "error": (
                "Music Recognition is not yet implemented. "
                "This endpoint is reserved for future integration."
            ),
        },
    )

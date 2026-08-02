"""
Recommendation router.

POST /recommend — delegates entirely to src.api.recommend().
The router only handles HTTP concerns (parsing, validation, response).
"""

import sys
import os

# Ensure src/ is on the import path so we can import the stable library.
_src_dir = os.path.join(os.path.dirname(__file__), "..", "..", "src")
if _src_dir not in sys.path:
    sys.path.insert(0, _src_dir)

from fastapi import APIRouter

from backend.exception_handlers import LyraException
from backend.models import RecommendRequest, RecommendResponse

router = APIRouter(tags=["recommendation"])


@router.post("/recommend", response_model=RecommendResponse)
def recommend(request: RecommendRequest):
    """Recommend songs based on the user's natural-language input.

    Delegates to the stable ``src.api.recommend()`` function.
    Returns the full pipeline result as structured JSON.
    """
    try:
        from api import recommend as _recommend
    except ImportError as e:
        raise LyraException(
            "Recommendation module not available",
            detail=f"Could not import src.api: {e}",
        )

    try:
        result = _recommend(request.user_input)
    except Exception as e:
        raise LyraException(
            "Recommendation pipeline failed",
            detail=str(e),
        )

    return RecommendResponse(**result)

"""
Feedback router.

POST /feedback — stores user feedback via src.feedback.FeedbackStore.
"""

import sys
import os

_src_dir = os.path.join(os.path.dirname(__file__), "..", "..", "src")
if _src_dir not in sys.path:
    sys.path.insert(0, _src_dir)

from fastapi import APIRouter

from backend.exception_handlers import LyraException
from backend.models import FeedbackRequest, FeedbackResponse

router = APIRouter(tags=["feedback"])


@router.post("/feedback", response_model=FeedbackResponse)
def submit_feedback(request: FeedbackRequest):
    """Record user feedback for a recommendation session.

    Feedback is appended to ``feedback.jsonl`` in the project root.
    """
    try:
        from feedback import FeedbackStore
    except ImportError as e:
        raise LyraException(
            "Feedback module not available",
            detail=f"Could not import src.feedback: {e}",
        )

    try:
        store = FeedbackStore()
        # The FeedbackStore.save() expects full recommendation dicts.
        # When called from the API, we reconstruct minimal dicts from
        # the song titles the client sends back.
        minimal_recs = [
            {"title": t, "id": "", "artist": ""} for t in request.song_titles
        ]
        store.save(
            user_query=request.user_query,
            intent={},  # intent not available at feedback time from thin API
            recommendations=minimal_recs,
            ratings=request.ratings,
            comment=request.comment,
        )
    except Exception as e:
        raise LyraException(
            "Failed to save feedback",
            detail=str(e),
        )

    return FeedbackResponse()

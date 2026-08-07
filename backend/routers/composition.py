"""
Composition router.

POST /composition — delegates to src.composition.Composer.

Accepts a text prompt with optional creative parameters and returns
a composition result. Currently the composer is a placeholder; when the
teammate's model is ready, only ``service.py`` needs to change — this
router stays the same.
"""

import sys
import os

_src_dir = os.path.join(os.path.dirname(__file__), "..", "..", "src")
if _src_dir not in sys.path:
    sys.path.insert(0, _src_dir)

from fastapi import APIRouter

from backend.exception_handlers import LyraException
from backend.models import CompositionData, CompositionRequest, CompositionResponse

router = APIRouter(tags=["composition"])


@router.post("/composition", response_model=CompositionResponse)
def compose(request: CompositionRequest):
    """Generate original music from a text prompt.

    **Placeholder:** currently returns an empty result. The real
    generation model will be integrated by replacing
    ``src/composition/service.py``.
    """
    # ── Import the composer ─────────────────────────────────────────
    try:
        from composition import Composer
    except ImportError as e:
        raise LyraException(
            "Composition module not available",
            detail=f"Could not import src.composition: {e}",
        )

    # ── Delegate to service layer ───────────────────────────────────
    try:
        composer = Composer()
        result = composer.generate(
            prompt=request.prompt,
            duration=request.duration,
            style=request.style or "",
            tempo=request.tempo or 0,
            key=request.key or "",
        )
    except Exception as e:
        raise LyraException(
            "Composition failed",
            detail=str(e),
        )

    # ── Build response ──────────────────────────────────────────────
    return CompositionResponse(
        data=CompositionData(**result),
        message="Composition service placeholder"
        if result.get("audio_url") is None
        else "Composition completed",
    )

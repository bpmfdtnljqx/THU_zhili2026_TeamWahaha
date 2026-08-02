"""
Lyra Backend — FastAPI application factory.

Thin HTTP layer wrapping the recommendation module in src/.
All business logic stays in src/api.py and its dependencies.
"""

import os
import sys

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

# Ensure src/ is importable.
_src_dir = os.path.join(os.path.dirname(__file__), "..", "src")
if _src_dir not in sys.path:
    sys.path.insert(0, _src_dir)


def create_app() -> FastAPI:
    """Build and configure the FastAPI application.

    Returns a fully configured app instance ready for ``uvicorn``.
    """
    app = FastAPI(
        title="Lyra — AI Music Recommendation",
        description=(
            "Backend API for the Lyra music companion. "
            "Provides recommendation, feedback, and placeholder endpoints "
            "for future Recognition and Composition modules."
        ),
        version="1.0.0",
        docs_url="/docs",
        redoc_url="/redoc",
    )

    # ── CORS — allow frontend access ─────────────────────────────────
    app.add_middleware(
        CORSMiddleware,
        allow_origins=os.getenv("LYRA_CORS_ORIGINS", "*").split(","),
        allow_credentials=True,
        allow_methods=["*"],
        allow_headers=["*"],
    )

    # ── Exception handlers — centralized, returns structured JSON ────
    from backend.exception_handlers import register_handlers

    register_handlers(app)

    # ── Routes ───────────────────────────────────────────────────────
    from backend.routers import recommend, feedback, recognition, composition

    app.include_router(recommend.router)
    app.include_router(feedback.router)
    app.include_router(recognition.router)
    app.include_router(composition.router)

    # ── Health check ─────────────────────────────────────────────────
    @app.get("/health", tags=["health"])
    def health():
        """Lightweight health check.

        Returns module status so the frontend can discover which features
        are available without probing every endpoint.
        """
        return {
            "status": "ok",
            "version": "1.0.0",
            "modules": {
                "recommendation": "stable",
                "recognition": "not_implemented",
                "composition": "not_implemented",
            },
        }

    return app


# Module-level app instance — what uvicorn imports.
# Usage: ``uvicorn backend.app:app --reload``
app = create_app()

"""
Lyra Backend — FastAPI application factory.

Thin HTTP layer wrapping the recommendation and recognition modules.
Business logic stays in src/ and the corresponding service/provider layers.
"""

import os
import sys
from pathlib import Path

from dotenv import load_dotenv

# Load .env before any config values are read.
load_dotenv()

from fastapi import FastAPI
from fastapi.staticfiles import StaticFiles
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
            "Provides recommendation, feedback, cloud-based music "
            "recognition, and composition endpoints."
        ),
        version="1.0.0",
        docs_url="/docs",
        redoc_url="/redoc",
    )

    # ── Static generated audio ────────────────────────────────────────
    # Composition service saves generated audio under
    # static/generated/<uuid>.mp3. Mount /static so the frontend can
    # play those files through the browser.
    static_dir = (
        Path(os.path.dirname(__file__))
        .resolve()
        .parent
        / "static"
    )
    generated_dir = static_dir / "generated"
    generated_dir.mkdir(parents=True, exist_ok=True)

    app.mount(
        "/static",
        StaticFiles(directory=str(static_dir)),
        name="static",
    )

    # ── CORS ─────────────────────────────────────────────────────────
    app.add_middleware(
        CORSMiddleware,
        allow_origins=os.getenv("LYRA_CORS_ORIGINS", "*").split(","),
        allow_credentials=True,
        allow_methods=["*"],
        allow_headers=["*"],
    )

    # ── Exception handlers ──────────────────────────────────────────
    from backend.exception_handlers import register_handlers

    register_handlers(app)

    # ── Routes ───────────────────────────────────────────────────────
    from backend.routers import (
        recommend,
        feedback,
        recognition,
        composition,
    )

    app.include_router(recommend.router)
    app.include_router(feedback.router)
    app.include_router(recognition.router)
    app.include_router(composition.router)

    # ── Health check ────────────────────────────────────────────────
    @app.get("/health", tags=["health"])
    def health():
        """Lightweight health check.

        Returns module status so the frontend can discover which features
        are currently available.
        """
        return {
            "status": "ok",
            "version": "1.0.0",
            "modules": {
                "recommendation": "stable",
                "recognition": "stable",
                "composition": "stable",
            },
        }

    return app


# Module-level app instance — what uvicorn imports.
#
# Usage:
#     uvicorn backend.app:app --reload
#
app = create_app()

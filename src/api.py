"""
api.py
------
Thin, importable API wrapper for the Lyra recommendation engine.

Designed for easy integration with future frontends (FastAPI, Flask, etc.).

Usage::

    from api import recommend, chat

    # Structured output (for API / frontend):
    result = recommend("今天心情很低落")
    # → fully JSON-serializable dict with intent, candidates, results, etc.

    # Display-ready string (for CLI or text responses):
    text = chat("今天心情很低落")
    # → formatted multi-line string
"""

from typing import Any, Dict

from agent import LyraAgent

# Module-level singleton — initialized lazily so the heavy model loading
# only happens on the first call, not at import time.
_agent: LyraAgent = None


def _get_agent() -> LyraAgent:
    """Get or create the singleton LyraAgent instance."""
    global _agent
    if _agent is None:
        _agent = LyraAgent()
    return _agent


def recommend(user_input: str) -> Dict[str, Any]:
    """Run the full recommendation pipeline.

    Returns a fully JSON-serializable dict::

        {
            "intent": {...},
            "candidates": [...],
            "ranked_results": [...],
            "response_text": "...",
            "metadata": {
                "pipeline_time_s": 3.5,
                "stages": {"planner_s": 0.8, ...},
                "candidate_count": 15,
                "result_count": 5,
                "cache_info": {...}
            }
        }
    """
    return _get_agent().recommend(user_input)


def chat(user_input: str) -> str:
    """Run the full pipeline, return a display-ready string.

    Convenience wrapper for when you only need the response text.
    """
    return _get_agent().chat(user_input)

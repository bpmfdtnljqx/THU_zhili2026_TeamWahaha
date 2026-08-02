"""
agent.py
--------
LyraAgent — lightweight orchestrator for the Lyra music recommendation
pipeline.

Coordinates: Planner → Retriever → Reranker → Response

Design principles
------------------
- No external Agent frameworks (LangChain, LangGraph, etc.).
- The Agent only wires components together — it contains no business
  logic, no retrieval logic, and no ranking logic.
- Each component is independently testable and replaceable.
- Two public methods:
  - ``recommend()`` returns a fully JSON-serializable dict (for API / frontend).
  - ``chat()`` returns a display-ready string (for CLI, backward-compatible).

Debug mode
----------
Set ``LYRA_DEBUG=1`` in the environment (or ``.env``) to enable
pipeline observability.  Debug output is written to **stderr** so it
does not interfere with the terminal spinner or normal CLI output.
"""

import json
import os
import sys
import time
from typing import Any, Dict, List, Optional

from planner import Planner
from retriever import Retriever
from reranker import DeepSeekReranker
from response_llm import LLMResponse
from logger import get_logger

# ---------------------------------------------------------------------------
# Logger
# ---------------------------------------------------------------------------

_log = get_logger("agent")

# Section width used for debug dividers — wide enough to be scannable
# but narrow enough to fit comfortably in a standard terminal.
_DIVIDER = "=" * 60


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _make_serializable(obj: Any) -> Any:
    """Recursively convert values to JSON-serializable types.

    Handles numpy scalars (common from chromadb distance values) and
    ensures all floats are rounded to a reasonable precision.
    """
    if isinstance(obj, dict):
        return {k: _make_serializable(v) for k, v in obj.items()}
    if isinstance(obj, (list, tuple)):
        return [_make_serializable(v) for v in obj]
    if hasattr(obj, "item"):  # numpy scalar (float32, int64, etc.)
        val = obj.item()
        if isinstance(val, float):
            return round(val, 6)
        return val
    if isinstance(obj, float):
        return round(obj, 6)
    return obj


def _debug_section(title: str) -> None:
    """Print a labelled debug section header to stderr."""
    _log.debug("")
    _log.debug(_DIVIDER)
    _log.debug(f"[DEBUG] {title}")
    _log.debug(_DIVIDER)


def _debug_kv(label: str, value: str) -> None:
    """Print a key-value pair in debug output."""
    _log.debug(f"  {label}: {value}")


# ---------------------------------------------------------------------------
# LyraAgent
# ---------------------------------------------------------------------------


class LyraAgent:
    """Orchestrate the full music-recommendation pipeline.

    Usage::

        agent = LyraAgent()

        # For structured output (API / frontend):
        result = agent.recommend("加班到凌晨，不想听太吵的歌")
        # result is a fully JSON-serializable dict

        # For display-ready string (CLI, backward-compatible):
        print(agent.chat("加班到凌晨，不想听太吵的歌"))
    """

    def __init__(self, verbose: bool = None):
        # Each component is initialised once and reused across calls.
        # Retriever is the heaviest (loads BGE-M3 + ChromaDB).
        self.planner = Planner(verbose=verbose)
        self.retriever = Retriever()
        self.reranker = DeepSeekReranker(verbose=verbose)
        self.responder = LLMResponse(verbose=verbose)

        self.verbose = verbose

    # ------------------------------------------------------------------
    # Public API
    # ------------------------------------------------------------------

    def recommend(self, user_input: str) -> Dict[str, Any]:
        """Run the full pipeline and return structured data.

        Parameters
        ----------
        user_input : str
            Raw natural-language input from the user
            (e.g. "失恋了，下雨的夜晚想一个人静静").

        Returns
        -------
        dict
            Fully JSON-serializable dict with keys:
            - **success**: ``True`` if the pipeline completed
            - **module**: ``"recommendation"``
            - **query**: the original user input
            - **intent**: structured intent from Planner
            - **recommendations**: Top-5 ranked songs with reasons
            - **response**: natural conversation response string
            - **timing**: per-stage timing breakdown
            - **metadata**: pipeline metadata (cache info, counts)
        """
        t_total = time.time()

        # ── Debug: user input ──
        if _log.enabled:
            _debug_section("User Input")
            _log.debug(user_input)

        # ── 1. Understand the user ──
        t0 = time.time()
        intent = self.planner.analyze(user_input)
        t_planner = round(time.time() - t0, 3)

        if _log.enabled:
            _debug_section("Planner Intent")
            printable = {k: v for k, v in intent.items() if k != "free_text"}
            _log.debug(json.dumps(printable, ensure_ascii=False, indent=2))

        # ── 2. Search ──
        t0 = time.time()
        query_text = intent.get("free_text", user_input)
        candidates = self.retriever.query(query_text, k=15)
        t_retriever = round(time.time() - t0, 3)

        if _log.enabled:
            _debug_section("Synthesized Retrieval Query")
            _log.debug(query_text)

            _debug_section("Retriever Results (top-k before reranking)")
            for i, c in enumerate(candidates, 1):
                title = c.get("title", "?")
                artist = c.get("artist", "?")
                distance = c.get("distance", "N/A")
                _log.debug(f"  {i:2d}. {title}  —  {artist}  [distance: {distance}]")

        # ── 3. Rank ──
        t0 = time.time()

        if _log.enabled:
            _debug_section("Reranker Input Context")
            _debug_kv("Original query", user_input)
            intent_summary = ", ".join(
                f"{k}={v}" for k, v in intent.items()
                if k != "free_text" and v
            )
            _debug_kv("Intent passed", intent_summary or "(empty intent)")
            _debug_kv("Candidates", str(len(candidates)))

        ranked = self.reranker.rerank(
            user_query=user_input,
            candidates=candidates,
            intent=intent,
        )
        t_reranker = round(time.time() - t0, 3)

        if _log.enabled:
            _debug_section("Final Ranking (before response generation)")
            for i, r in enumerate(ranked, 1):
                title = r.get("title", "?")
                artist = r.get("artist", "?")
                reason = r.get("reason", "")
                distance = r.get("distance", "N/A")
                _log.debug(f"  {i}. {title}  —  {artist}  [distance: {distance}]")
                if reason:
                    _log.debug(f"     reason: {reason}")
            _log.debug(_DIVIDER)

        # ── 4. Respond ──
        t0 = time.time()
        response_text = self.responder.generate(user_input, intent, ranked)
        t_response = round(time.time() - t0, 3)

        # ── Build result ──
        pipeline_time = round(time.time() - t_total, 3)
        timing = {
            "total_s": pipeline_time,
            "planner_s": t_planner,
            "retriever_s": t_retriever,
            "reranker_s": t_reranker,
            "response_s": t_response,
        }

        metadata = {
            "candidate_count": len(candidates),
            "result_count": len(ranked),
            "cache_info": self.reranker.cache_stats,
        }

        _log.debug(f"Pipeline complete in {pipeline_time:.3f}s "
                   f"(planner={t_planner:.3f} retriever={t_retriever:.3f} "
                   f"reranker={t_reranker:.3f} response={t_response:.3f})")

        return _make_serializable({
            "success": True,
            "module": "recommendation",
            "query": user_input,
            "intent": intent,
            "recommendations": ranked,
            "response": response_text,
            "timing": timing,
            "metadata": metadata,
        })

    def chat(self, user_input: str) -> str:
        """Run the full pipeline and return a display-ready string.

        This is a convenience wrapper around ``recommend()`` for backward
        compatibility with the CLI.

        Parameters
        ----------
        user_input : str
            Raw natural-language input from the user.

        Returns
        -------
        str
            Formatted multi-line string ready for terminal display.
        """
        result = self.recommend(user_input)
        return result["response"]

    # ------------------------------------------------------------------
    # Convenience
    # ------------------------------------------------------------------

    @property
    def cache_stats(self):
        """Expose reranker cache stats for monitoring."""
        return self.reranker.cache_stats

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
- Single public method: ``chat()`` returns a display-ready string.
"""

from typing import Dict, List

from planner import Planner
from retriever import Retriever
from reranker import DeepSeekReranker
from response import Response


class LyraAgent:
    """Orchestrate the full music-recommendation pipeline.

    Usage::

        agent = LyraAgent()
        print(agent.chat("加班到凌晨，不想听太吵的歌"))
    """

    def __init__(self, verbose: bool = None):
        # Each component is initialised once and reused across calls.
        # Retriever is the heaviest (loads BGE-M3 + ChromaDB).
        self.planner = Planner(verbose=verbose)
        self.retriever = Retriever()
        self.reranker = DeepSeekReranker(verbose=verbose)
        self.responder = Response()

        self.verbose = verbose

    # ------------------------------------------------------------------
    # Public API
    # ------------------------------------------------------------------

    def chat(self, user_input: str) -> str:
        """Run the full pipeline and return a display-ready string.

        Parameters
        ----------
        user_input : str
            Raw natural-language input from the user (e.g. "失恋了，下雨的夜晚想一个人静静").

        Returns
        -------
        str
            Formatted multi-line string ready for terminal display.
        """
        # ── 1. Understand the user ──
        intent = self.planner.analyze(user_input)

        if self.verbose:
            import json
            printable = {k: v for k, v in intent.items() if k != "free_text"}
            print(f"[Agent] Intent: {json.dumps(printable, ensure_ascii=False)}")

        # ── 2. Search ──
        # Use the synthesised free_text for embedding; it captures the
        # structured intent in natural language so BGE-M3 produces a
        # richer embedding than raw user input alone.
        query_text = intent.get("free_text", user_input)
        candidates = self.retriever.query(query_text, k=15)

        if self.verbose:
            print(f"[Agent] Retrieved {len(candidates)} candidates")

        # ── 3. Rank ──
        # Intent is passed as supplementary context.  The reranker
        # treats the original user query as the primary signal.
        ranked = self.reranker.rerank(
            user_query=user_input,
            candidates=candidates,
            intent=intent,
        )

        if self.verbose:
            titles = [r["title"] for r in ranked]
            print(f"[Agent] Ranked Top-{len(ranked)}: {titles}")

        # ── 4. Respond ──
        return self.responder.generate(user_input, intent, ranked)

    # ------------------------------------------------------------------
    # Convenience
    # ------------------------------------------------------------------

    @property
    def cache_stats(self):
        """Expose reranker cache stats for monitoring."""
        return self.reranker.cache_stats

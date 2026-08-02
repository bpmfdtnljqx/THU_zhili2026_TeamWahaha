"""
main.py
-------
CLI demo for the Lyra Agent.

If ./chroma_db does not exist, builds the index first.
Then enters an interactive query loop powered by ``LyraAgent``.
"""

import os
import sys
import threading
import time

from dotenv import load_dotenv
load_dotenv()

PERSIST_DIR = os.path.join(os.path.dirname(__file__), "..", "chroma_db")

# ── Spinner animation for "Thinking..." ──
SPINNER_CHARS = "⠋⠙⠹⠸⠼⠴⠦⠧⠇⠏"
SPINNER_DONE = False


def _spinner():
    """Simple terminal spinner — runs until SPINNER_DONE is set."""
    i = 0
    while not SPINNER_DONE:
        sys.stdout.write(f"\r  {SPINNER_CHARS[i % len(SPINNER_CHARS)]} Thinking...")
        sys.stdout.flush()
        time.sleep(0.08)
        i += 1
    # Clear the spinner line
    sys.stdout.write("\r" + " " * 30 + "\r")
    sys.stdout.flush()


def _collect_feedback(last_result):
    """Prompt the user for quick feedback on the recommendations.

    Saves feedback to ``feedback.jsonl`` via ``FeedbackStore``.
    """
    try:
        fb = input(
            "  [Feedback] Did these match your mood? (y/n/Enter=skip): "
        ).strip().lower()
    except (EOFError, KeyboardInterrupt):
        return

    if fb not in ("y", "n"):
        return

    try:
        from feedback import FeedbackStore
    except ImportError:
        return

    ranked = last_result["recommendations"]
    ratings: dict = {}

    if fb == "y":
        # All liked
        for r in ranked:
            ratings[r.get("title", "")] = "like"
        FeedbackStore().save(
            last_result.get("_query", ""),
            last_result["intent"],
            ranked,
            ratings,
        )
        print("  Thanks! Glad they resonated. :)")

    elif fb == "n":
        try:
            disliked = input(
                "  Which ones didn't fit? (numbers, e.g. 1,3): "
            ).strip()
        except (EOFError, KeyboardInterrupt):
            return

        dislike_indices = set()
        for part in disliked.replace("，", ",").split(","):
            part = part.strip()
            if part.isdigit():
                idx = int(part) - 1
                if 0 <= idx < len(ranked):
                    dislike_indices.add(idx)

        for i, r in enumerate(ranked):
            title = r.get("title", "")
            if i in dislike_indices:
                ratings[title] = "dislike"
            else:
                ratings[title] = "like"

        FeedbackStore().save(
            last_result.get("_query", ""),
            last_result["intent"],
            ranked,
            ratings,
        )
        print("  Thanks! I'll learn from this. :)")


def main():
    # Build index if needed
    if not os.path.isdir(PERSIST_DIR):
        print("No index found. Building...\n")
        from build_index import build_collection
        build_collection()
        print()

    # ── Init Agent (loads Planner, Retriever, Reranker, Response) ──
    print("Loading Lyra Agent...")
    from agent import LyraAgent
    agent = LyraAgent()
    print("Ready.\n")

    print("=" * 56)
    print("  🎵  Lyra — AI Music Recommendation Agent")
    print("  Describe your mood or situation, discover songs.")
    print("  Type 'quit' to exit.")
    print("=" * 56)
    print()

    global SPINNER_DONE
    last_result = None

    while True:
        try:
            query = input("> ").strip()
        except (EOFError, KeyboardInterrupt):
            print("\nBye!")
            break

        if not query:
            continue
        if query.lower() == "quit":
            print("Bye!")
            break

        # ── Run full pipeline (Planner → Retriever → Reranker → Response) ──
        SPINNER_DONE = False
        spinner_thread = threading.Thread(target=_spinner, daemon=True)
        spinner_thread.start()

        try:
            # Use recommend() to get structured data for feedback + display
            last_result = agent.recommend(query)
            last_result["_query"] = query  # stash for feedback
            response = last_result["response"]
        finally:
            SPINNER_DONE = True
            spinner_thread.join(timeout=0.5)

        print()
        print(response)
        print()

        # ── Quick feedback ──
        if last_result:
            _collect_feedback(last_result)
            print()


if __name__ == "__main__":
    main()

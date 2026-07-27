"""
main.py
-------
CLI demo for the Lyra Retrieval Engine.

If ./chroma_db does not exist, builds the index first.
Then enters an interactive query loop.
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


def main():
    # Build index if needed
    if not os.path.isdir(PERSIST_DIR):
        print("No index found. Building...\n")
        from build_index import build_collection
        build_collection()
        print()

    # Load retriever
    from retriever import Retriever
    retriever = Retriever()

    # Load reranker (lazy init on first query)
    reranker = None

    print()
    print("=" * 56)
    print("  🎵  Lyra — AI Music Recommendation Agent")
    print("  Describe your mood or situation, discover songs.")
    print("  Type 'quit' to exit.")
    print("=" * 56)
    print()

    global SPINNER_DONE

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

        # Step 1: Retrieve Top-15 candidates
        candidates = retriever.query(query, k=15)

        # Step 2: Rerank with DeepSeek (show spinner while working)
        if reranker is None:
            from reranker import DeepSeekReranker
            reranker = DeepSeekReranker()

        SPINNER_DONE = False
        spinner_thread = threading.Thread(target=_spinner, daemon=True)
        spinner_thread.start()

        try:
            results = reranker.rerank(query, candidates)
        finally:
            SPINNER_DONE = True
            spinner_thread.join(timeout=0.5)

        # ── Display results ──
        print()
        print("  " + "─" * 48)
        for i, r in enumerate(results, 1):
            print(f"  {i}.  {r['title']}  —  {r['artist']}")
            print(f"       {r['album']} ({r['year']})  |  {r['genre']}")
            if r.get("reason"):
                print(f"       💭 {r['reason']}")
            print()
        print("  " + "─" * 48)
        print()


if __name__ == "__main__":
    main()

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
            response = agent.chat(query)
        finally:
            SPINNER_DONE = True
            spinner_thread.join(timeout=0.5)

        print()
        print(response)
        print()


if __name__ == "__main__":
    main()

"""
main.py
-------
CLI demo for the Lyra Retrieval Engine.

If ./chroma_db does not exist, builds the index first.
Then enters an interactive query loop.
"""

import os
import sys

PERSIST_DIR = os.path.join(os.path.dirname(__file__), "..", "chroma_db")


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

    print()
    print("=" * 50)
    print("  Lyra — AI Music Recommendation Agent")
    print("  Type your feeling or situation, get songs.")
    print("  Type 'quit' to exit.")
    print("=" * 50)
    print()

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

        results = retriever.query(query, k=5)

        print()
        for i, r in enumerate(results, 1):
            print(f"  #{i}  {r['title']} — {r['artist']}")
            print(f"       {r['album']} ({r['year']}) | {r['genre']}")
            print(f"       距离: {r['distance']}")
            if r["reason"]:
                print(f"       推荐: {r['reason']}")
            print()
        print("-" * 50)
        print()


if __name__ == "__main__":
    main()

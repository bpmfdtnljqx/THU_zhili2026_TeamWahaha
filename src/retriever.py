"""
retriever.py
------------
Load a persisted ChromaDB collection and query it with
natural-language text to return Top-K song recommendations.
"""

import os
# === Force offline mode to avoid network checks ===
os.environ["HF_HUB_OFFLINE"] = "1"
os.environ["TRANSFORMERS_OFFLINE"] = "1"
os.environ["HF_ENDPOINT"] = ""

from sentence_transformers import SentenceTransformer
import chromadb

from logger import get_logger

_log = get_logger("retriever")

MODEL_NAME = "BAAI/bge-m3"
COLLECTION_NAME = "lyra_songs"
PERSIST_DIR = os.path.join(os.path.dirname(__file__), "..", "chroma_db")


class Retriever:
    def __init__(self, persist_dir: str = PERSIST_DIR):
        self.persist_dir = persist_dir

        _log.info(f"Loading embedding model {MODEL_NAME}...")
        self.model = SentenceTransformer(MODEL_NAME, trust_remote_code=False)

        _log.info(f"Loading ChromaDB collection from {persist_dir}...")
        self.client = chromadb.PersistentClient(path=persist_dir)
        self.collection = self.client.get_collection(COLLECTION_NAME)
        _log.info(f"Collection '{COLLECTION_NAME}' loaded ({self.collection.count()} songs).")

    def query(self, text: str, k: int = 5) -> list[dict]:
        """
        Embed a natural-language query and return Top-K results.

        Each result is a dict with:
          title, artist, album, year, genre, reason, distance
        """
        query_embedding = self.model.encode([text]).tolist()

        results = self.collection.query(
            query_embeddings=query_embedding,
            n_results=k,
        )

        output = []
        ids = results.get("ids", [[]])[0]
        distances = results.get("distances", [[]])[0]
        metadatas = results.get("metadatas", [[]])[0]

        for song_id, distance, meta in zip(ids, distances, metadatas):
            output.append({
                "id": song_id,
                "title": meta.get("title", ""),
                "artist": meta.get("artist", ""),
                "album": meta.get("album", ""),
                "year": meta.get("year", ""),
                "genre": meta.get("genre", ""),
                "reason": meta.get("reason", ""),
                "distance": round(distance, 4),
            })

        return output

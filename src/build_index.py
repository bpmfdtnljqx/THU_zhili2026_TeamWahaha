"""
build_index.py
-------------
Read songs.json, construct embedding text for each song,
generate embeddings with BGE-M3, and persist to ChromaDB.
"""

import json
import os

from dotenv import load_dotenv
load_dotenv()

from sentence_transformers import SentenceTransformer
import chromadb


SONGS_PATH = os.path.join(os.path.dirname(__file__), "..", "songs.json")
PERSIST_DIR = os.path.join(os.path.dirname(__file__), "..", "chroma_db")
MODEL_NAME = "BAAI/bge-m3"
COLLECTION_NAME = "lyra_songs"


def load_songs(path: str) -> list[dict]:
    with open(path, "r", encoding="utf-8") as f:
        return json.load(f)


def build_embedding_text(song: dict) -> str:
    """
    Combine key fields into a natural-language paragraph
    that captures the song's full semantic profile.
    """
    parts = []

    description = song.get("description", "")
    if description:
        parts.append(description)

    core_theme = song.get("core_theme", [])
    if core_theme:
        parts.append(f"歌曲主题：{'、'.join(core_theme)}。")

    emotion = song.get("emotion", [])
    if emotion:
        parts.append(f"情绪感受：{'、'.join(emotion)}。")

    suitable_scene = song.get("suitable_scene", [])
    if suitable_scene:
        parts.append(f"适合场景：{'、'.join(suitable_scene)}。")

    listener_need = song.get("listener_need", [])
    if listener_need:
        parts.append(f"听众需要：{'、'.join(listener_need)}。")

    return " ".join(parts)


def build_collection():
    print(f"Loading songs from {SONGS_PATH}...")
    songs = load_songs(SONGS_PATH)
    print(f"Loaded {len(songs)} songs.")

    print(f"Loading embedding model {MODEL_NAME} (first run will download ~2GB)...")
    model = SentenceTransformer(MODEL_NAME)

    texts = []
    metadatas = []
    ids = []

    for i, song in enumerate(songs):
        text = build_embedding_text(song)
        texts.append(text)
        metadatas.append({
            "title": song.get("title", ""),
            "artist": song.get("artist", ""),
            "album": song.get("album", ""),
            "year": str(song.get("year", "")),
            "genre": song.get("genre", ""),
            "reason": song.get("recommendation_reason", ""),
        })
        ids.append(str(i))

    print(f"Embedding {len(songs)} songs (this may take a while on CPU)...")
    embeddings = model.encode(texts, show_progress_bar=True)

    print(f"Persisting to {PERSIST_DIR}...")
    client = chromadb.PersistentClient(path=PERSIST_DIR)
    collection = client.get_or_create_collection(
        name=COLLECTION_NAME,
        metadata={"hnsw:space": "cosine"},
    )

    collection.add(
        embeddings=embeddings.tolist(),
        documents=texts,
        metadatas=metadatas,
        ids=ids,
    )

    print(f"Done. {collection.count()} songs indexed in '{COLLECTION_NAME}'.")
    return collection


if __name__ == "__main__":
    build_collection()

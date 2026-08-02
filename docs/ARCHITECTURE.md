# Lyra Architecture

> Version: 1.0
> Date: 2026-08-02
> Status: **Recommendation — Stable. Recognition / Composition — Planned.**

---

## High-level Overview

Lyra is an AI-powered music assistant built around three independent capabilities:

```
┌──────────────────────────────────────────────────┐
│                    LyraAgent                      │
│                  (Orchestrator)                   │
├──────────────────────────────────────────────────┤
│                    Planner                        │
│             (Intent Understanding)                │
├──────────────────┬─────────────────┬──────────────┤
│  Recommendation  │   Recognition   │  Composition │
│    (v1.0 ✅)     │   (Planned 🚧)  │ (Planned 🚧) │
└──────────────────┴─────────────────┴──────────────┘
```

Each capability is developed independently, has its own data dependencies and models, and communicates through a shared JSON response envelope. The Planner acts as a router: it understands what the user wants and delegates to the appropriate module.

---

## System Components

### LyraAgent (Orchestrator)

**Status:** Implemented.

The Agent wires components together. It does not contain business logic — it only coordinates data flow.

Currently the Agent always routes to Recommendation (the only implemented capability). When Recognition and Composition are added, the Agent will use Planner intent to decide which module to invoke.

Location: `src/agent.py`

### Planner (Intent Understanding)

**Status:** Implemented.

The Planner extracts structured intent from natural-language user input via the DeepSeek API. It understands *what the user wants to do* — not just their emotional state.

Currently the Planner extracts music-listening intent (emotion, scene, listener_need, energy_level, avoid). When Recognition and Composition are added, the Planner will also detect *action intent* — e.g., "identify this song" vs "create a song" vs "recommend something."

Location: `src/planner.py`

### Recommendation Module

**Status:** Stable (v1.0). ✅

The complete recommendation pipeline:

```
Planner → Retriever (BGE-M3 + ChromaDB) → Reranker (DeepSeek) → LLMResponse (DeepSeek)
                                                    ↓ (on failure)
                                            Template Response (fallback)
```

Returns Top-5 songs with personalized reasons and a warm natural-language response.

Components: `retriever.py`, `reranker.py`, `reranker_cache.py`, `response_llm.py`, `response.py`

API: `recommend(user_input) -> dict` (documented in `API_SPEC.md`)

### Recognition Module

**Status:** Planned. 🚧

Will identify songs from audio input (humming, recording, upload). Likely components: audio fingerprinting, acoustic fingerprint database, candidate ranking.

Expected API: `recognize(audio, sample_rate) -> dict`

Interface contract documented in `API_SPEC.md` (Reserved section).

### Composition Module

**Status:** Planned. 🚧

Will generate original music from user prompts. Likely components: music generation model, style conditioning, audio encoding.

Expected API: `compose(prompt, style, duration_s) -> dict`

Interface contract documented in `API_SPEC.md` (Reserved section).

### API Layer

**Status:** Implemented (for Recommendation). Partial.

`src/api.py` provides a thin, importable wrapper around LyraAgent. It uses a module-level singleton with lazy initialization so heavy models load only on first use.

Future state: `api.py` will expose `recommend()`, `recognize()`, and `compose()` — each delegating to the appropriate module through the Planner.

### Frontend

**Status:** Planned. 🚧

The frontend consumes the stable JSON API. Because all modules share the same response conventions, the frontend can render results from any module without module-specific code.

---

## Interaction Flow

### Flow 1: Music Recommendation

```
User: "加班到凌晨，不想听太吵的歌"
        │
        ▼
    Planner.analyze()
        │  intent: {action: "recommend", emotion: ["疲惫"], ...}
        ▼
    Recommendation.recommend()
        │  Planner → Retriever → Reranker → LLMResponse
        ▼
    Response
        {
          "success": true,
          "module": "recommendation",
          "recommendations": [...],
          "response": "加班到深夜的滋味我太懂了..."
        }
```

### Flow 2: Music Recognition (Planned)

```
User: [uploads audio] "这是什么歌？"
        │
        ▼
    Planner.analyze()
        │  intent: {action: "recognize", ...}
        ▼
    Recognition.recognize(audio)
        │  fingerprint → search → rank
        ▼
    Response
        {
          "success": true,
          "module": "recognition",
          "results": [{"title": "夜曲", "confidence": 0.95}]
        }
```

### Flow 3: AI Composition (Planned)

```
User: "帮我写一首毕业歌，温馨一点的"
        │
        ▼
    Planner.analyze()
        │  intent: {action: "compose", style: "温馨", scene: "毕业", ...}
        ▼
    Composition.compose(prompt, style, ...)
        │  generate → encode → upload
        ▼
    Response
        {
          "success": true,
          "module": "composition",
          "audio_url": "https://..."
        }
```

---

## Design Principles

### 1. Loose Coupling

Modules share no runtime dependencies. Recommendation does not import Recognition. Each module can be developed, tested, and deployed independently.

The only shared code is:
- `logger.py` — optional structured logging
- The common response envelope (`success`, `module`, `timing`, `metadata`)

### 2. Stable Interfaces

Once a module reaches v1.0, its public contract is frozen. New fields may be added; existing fields are never removed or renamed without a major version bump.

The Recommendation API is already frozen (see `docs/API_SPEC.md`).

### 3. Module Independence

Each module owns its own:
- Data dependencies (songs.json for Recommendation, fingerprint DB for Recognition, etc.)
- Models (BGE-M3 for Recommendation, audio model for Recognition, etc.)
- Configuration (API keys, model paths, etc.)

### 4. JSON-First Communication

All module inputs and outputs are JSON-serializable. No pickled objects, no platform-specific binary formats, no internal Python types crossing module boundaries.

### 5. Single Responsibility

- **Planner**: understand what the user wants
- **Recommendation**: recommend songs
- **Recognition**: identify songs
- **Composition**: generate songs
- **Agent**: wire components together
- **API layer**: expose stable public interfaces
- **Frontend**: render results

No module does two things.

### 6. Future Extensibility

New capabilities are added as new modules — not as modifications to existing ones. The Planner learns to detect new action intents. The API layer gains new functions. The common response envelope stays the same. Existing modules stay untouched.

---

## Module Responsibility Boundaries

```
                          User Input
                              │
                              ▼
                          Planner
                   "What does the user want?"
                              │
              ┌───────────────┼───────────────┐
              │               │               │
              ▼               ▼               ▼
       Recommendation    Recognition     Composition
       "Find songs"    "Name that song"  "Make music"
              │               │               │
              └───────────────┼───────────────┘
                              ▼
                         Response
              (Common JSON envelope, natural language)
```

**Recommendation** is responsible ONLY for:
- Understanding music-listening intent
- Semantic retrieval from the song knowledge base
- Ranking and explaining recommendations
- Generating empathetic natural-language responses

**Recognition** will be responsible ONLY for:
- Processing audio input
- Generating acoustic fingerprints
- Matching against a reference database
- Returning ranked matches with confidence scores

**Composition** will be responsible ONLY for:
- Interpreting creative prompts
- Generating original audio
- Encoding and returning the result

**The Planner** decides which module handles a given request. When only Recommendation exists, all inputs route to it. When multiple modules exist, the Planner detects action intent to route correctly.

---

## Future Expansion

New capabilities can be added without modifying existing modules by following this pattern:

### Adding a new module (e.g., Playlist Generation)

1. Define the API contract in `docs/API_SPEC.md` under a new reserved section
2. Implement the module in `src/playlist.py` with a single public function returning the common envelope
3. Teach the Planner to detect `action: "playlist"` intent
4. Add routing logic in the Agent: `if intent.action == "playlist": return Playlist.generate(...)`
5. Expose via `src/api.py`: `def generate_playlist(user_input) -> dict`

No existing module code changes. No shared base classes needed. The common envelope is the only contract.

### Potential future modules

| Module | Purpose | Input | Dependencies |
|--------|---------|-------|-------------|
| Playlist Generation | Create multi-song playlists | NL prompt | Recommendation + sequencing logic |
| Lyrics Analysis | Analyze song lyrics for meaning | Song title / lyrics text | NLP model |
| Music Search | Find songs by descriptors | NL query | Vector search over expanded DB |
| Mood Journal | Track emotional-music patterns over time | Feedback history | feedback.jsonl |

None of these require changes to the existing Recommendation module.

---

## Current Code Layout

```
lyra/
├── docs/
│   ├── API_SPEC.md          # Frozen API contract
│   └── ARCHITECTURE.md       # This document
├── src/
│   ├── agent.py             # LyraAgent orchestrator
│   ├── planner.py           # Intent extraction (DeepSeek)
│   ├── retriever.py         # BGE-M3 + ChromaDB vector search
│   ├── reranker.py          # DeepSeek re-ranking + avoid filtering
│   ├── reranker_cache.py    # LRU + TTL memory cache
│   ├── response_llm.py      # LLM natural conversation (DeepSeek)
│   ├── response.py          # Template-based fallback
│   ├── feedback.py          # User feedback storage (JSONL)
│   ├── logger.py            # Structured logging
│   ├── api.py               # Public API wrapper
│   ├── build_index.py       # One-shot ChromaDB index builder
│   ├── benchmark.py         # Performance + quality benchmark
│   └── main.py              # CLI demo
├── songs.json               # Music knowledge base (170 songs)
├── feedback.jsonl           # User feedback data
└── chroma_db/               # Vector database (generated)
```

---

## Integration Readiness Assessment

The current architecture is integration-ready as-is. Specifically:

1. **The common response envelope** (`success`, `module`, `timing`, `metadata`) is already defined and documented. New modules just need to return it.

2. **The API layer** (`src/api.py`) is a single import point. Adding `recognize()` and `compose()` alongside `recommend()` is trivial.

3. **The Planner** already extracts structured intent. Adding action detection ("recommend" vs "recognize" vs "compose") is a prompt engineering change, not an architecture change.

4. **No abstract base classes are needed.** The common contract is a data format (the JSON envelope), not a class hierarchy. Each module is a plain function returning a dict — the simplest possible interface.

5. **No placeholder modules are needed.** They would add maintenance burden without value. The API_SPEC.md reserved sections already serve as the contract for future implementers.

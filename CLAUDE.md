# Lyra

## Project Overview

Lyra is an AI-powered music recommendation agent.

The goal is not keyword matching.

The goal is semantic understanding of user emotions and life situations, then recommending meaningful music.

**This is a university AI music assistant competition project.**

---

## Current Project Status

**Multi-module platform — Recommendation complete, Recognition integrated, Composition pending.**

### Module 1: Recommendation (COMPLETE — do NOT rebuild)

Completed pipeline:

- Planner — intent extraction (DeepSeek API)
- Retriever — semantic search (BGE-M3 + ChromaDB)
- Reranker — AI ranking with avoid filtering + diversity control (DeepSeek API)
- LLMResponse — natural, empathetic conversation (DeepSeek API)
- Response — template-based fallback for graceful degradation
- FeedbackStore — JSONL persistence for future personalization
- Structured logging — unified pipeline observability
- API wrapper — `recommend()` returns structured JSON-serializable data
- Enhanced benchmark — diversity metrics, LLM judge, pipeline timing

Completed backend service:

- FastAPI backend (`backend/`) — thin HTTP layer on top of `src/`
- REST API endpoints: `GET /health`, `POST /recommend`, `POST /feedback`, `POST /recognition`, `POST /composition`
- Smoke tests pass with full recommendation pipeline

Completed frontend demo:

- Lightweight single-page demo (`frontend/index.html`)
- User input → recommendation → song cards → feedback interaction
- Backend health status display
- Request timeout + duplicate request prevention

### Module 2: Recognition (INTEGRATED)

- FastAPI recognition endpoint (`POST /recognition`) — active, not placeholder
- Recognition service layer (`src/recognition/service.py`) — engine abstraction
- Auris HTTP provider (`src/recognition/providers/auris.py`) — Docker engine communication
- Graceful fallback when Auris is unavailable
- Auris engine at `auris-engine/` — external Rust Docker project (do NOT modify)

Current gaps:
- Auris fingerprint database needs song data preparation
- End-to-end recognition testing pending fingerprint DB

### Module 3: Composition (INTERFACE ONLY)

- API endpoint defined (`POST /composition`) — placeholder response
- Composition service layer (`src/composition/service.py`) — stub with full replacement guide
- Waiting for teammate model integration

---

## Architecture

```
Frontend (Demo)
    │
    ▼
FastAPI Backend
    │
    ├── /recommend    → src/agent.py → Planner → Retriever → Reranker → LLMResponse
    ├── /recognition  → src/recognition/service.py → AurisProvider (HTTP) → Auris Engine (Docker)
    └── /composition  → src/composition/service.py → placeholder
```

Key modules:

- `src/agent.py` — LyraAgent orchestrator (stable, do not redesign)
- `src/planner.py` — Intent extraction
- `src/retriever.py` — BGE-M3 + ChromaDB retrieval
- `src/reranker.py` — DeepSeek reranking with avoid + diversity
- `src/response_llm.py` — LLM natural conversation
- `src/response.py` — Template fallback
- `src/recognition/` — Recognition module (engine abstraction + providers)
- `src/composition/` — Composition module (placeholder)
- `backend/` — FastAPI HTTP layer
- `frontend/` — Demo SPA
- `auris-engine/` — External Auris fingerprint engine (do NOT modify)

---

## Development Principles

Always follow these principles.

### 1. Semantic Retrieval

Do NOT implement keyword matching.

Always use semantic embedding.

### 2. Agent First

Lyra is an AI Agent.

Avoid writing business logic directly into frontend.

Keep retrieval, reasoning and response generation independent.

### 3. Music Knowledge Base

songs.json is the source of truth.

Never overwrite it automatically.

If new fields are needed, generate them dynamically.

### 4. Code Style

Prefer simple architecture.

Avoid over-engineering.

Avoid unnecessary frameworks.

### 5. Stable Architecture

The pipeline is stable: Planner → Retriever → Reranker → LLMResponse.

Do not redesign the pipeline without explicit approval.

Prefer small incremental improvements over large rewrites.

Keep modules loosely coupled. Keep each component focused on a single responsibility.

Preserve backward compatibility whenever possible.

### 6. Development Priorities

1. **Integration** — connect existing modules, don't build new ones
2. **Reliability** — graceful degradation, error handling, fallback paths
3. **Testing** — verify integrations work end-to-end
4. **Competition preparation** — stable demo, polished UX, documentation

---

## Important Rules

### Do NOT:

- Do NOT rebuild the completed recommendation system
- Do NOT introduce unnecessary frameworks or architectural abstractions
- Do NOT redesign the pipeline architecture
- Do NOT move src modules or rename Python packages
- Do NOT change import paths or module structures
- Do NOT modify backend API contracts without approval
- Do NOT modify frontend code without approval
- Do NOT modify auris-engine/ (external project)
- Do NOT add new features without explicit approval
- Do NOT refactor without approval

### DO:

- Prefer incremental integration over new features
- Protect stable APIs and existing contracts
- Fix bugs when found
- Update documentation when making changes
- Add tests for new integration points
- Use graceful fallback for external dependencies
- Keep the codebase clean and well-documented

---

## Repository Structure

```
lyra/
├── src/                    # Core business logic (stable)
│   ├── agent.py            #   LyraAgent orchestrator
│   ├── planner.py          #   Intent extraction
│   ├── retriever.py        #   BGE-M3 + ChromaDB
│   ├── reranker.py         #   DeepSeek reranking
│   ├── reranker_cache.py   #   LRU cache
│   ├── response_llm.py     #   LLM conversation
│   ├── response.py         #   Template fallback
│   ├── feedback.py         #   Feedback persistence
│   ├── logger.py           #   Structured logging
│   ├── api.py              #   Thin API wrapper
│   ├── build_index.py      #   Index builder
│   ├── benchmark.py        #   Performance tests
│   ├── main.py             #   CLI entry point
│   ├── recognition/        #   Recognition module
│   │   ├── service.py      #     Recognizer engine
│   │   └── providers/      #     Engine adapters
│   │       └── auris.py    #       Auris HTTP provider
│   └── composition/        #   Composition module
│       └── service.py      #     Composer stub
├── backend/                # FastAPI service layer
│   ├── app.py              #   App factory + CORS
│   ├── models.py           #   Pydantic models
│   ├── routers/            #   API routes
│   └── smoke_test.py       #   E2E smoke test
├── frontend/               # Demo SPA
│   └── index.html
├── auris-engine/           # Auris engine (do NOT modify)
├── docs/                   # Technical documentation
├── songs.json              # Music knowledge base
├── requirements.txt        # Python dependencies
└── .env                    # Environment variables (gitignored)
```

---

## Current Focus

The project is in **competition preparation** phase:

1. Ensure Recommendation demo works reliably
2. Build Auris fingerprint database for Recognition demo
3. Integrate Composition model when teammate delivers
4. Polish demo flow and error handling
5. Update documentation for competition judges

**Stability > Features. Reliability > Novelty. Integration > New development.**

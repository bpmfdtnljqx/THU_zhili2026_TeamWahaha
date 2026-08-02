# Lyra

## Project Overview

Lyra is an AI-powered music recommendation agent.

The goal is not keyword matching.

The goal is semantic understanding of user emotions and life situations, then recommending meaningful music.

---

## Current Project Status

**Recommendation backend is feature complete.**

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

Not yet implemented:

- Frontend / chat UI
- Music Recognition (independent module)
- AI Composition (independent module)
- Feedback-driven personalization

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

### 6. Current Milestone

Recommendation backend is feature complete.

Future work should focus on:

- Quality improvements to recommendations and responses
- Maintainability and code health
- Frontend integration (clean APIs are already in place via `api.py`)
- Integration with future Recognition and Composition modules
- Feedback-driven personalization

Do not implement Recognition or Composition unless explicitly requested.

Do not start frontend unless explicitly requested.

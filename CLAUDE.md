# Lyra

## Project Overview

Lyra is an AI-powered music recommendation agent.

The goal is not keyword matching.

The goal is semantic understanding of user emotions and life situations, then recommending meaningful music.

---

## Current Project Status

Completed:

- Music Knowledge Base (songs.json)
- Around 170 curated Chinese songs
- Structured metadata
- Product design
- Recommendation workflow

Not implemented yet:

- Embedding
- Vector Database
- Retrieval Engine
- Recommendation Agent
- Frontend

---

## Development Principles

Always follow these principles.

### 1. Semantic Retrieval

Do NOT implement keyword matching.

Always use semantic embedding.

---

### 2. Agent First

Lyra is an AI Agent.

Avoid writing business logic directly into frontend.

Keep retrieval, reasoning and response generation independent.

---

### 3. Music Knowledge Base

songs.json is the source of truth.

Never overwrite it automatically.

If new fields are needed,
generate them dynamically.

---

### 4. Code Style

Prefer simple architecture.

Avoid over-engineering.

Avoid unnecessary frameworks.

---

### 5. Current Milestone

Current task:

Build Retrieval Engine.

Requirements:

- Read songs.json
- Generate embedding text
- Build vector database
- Retrieve Top-K songs
- Easy to extend into Agent

Do not start frontend.

Do not build chat UI.

Focus on backend AI capability first.
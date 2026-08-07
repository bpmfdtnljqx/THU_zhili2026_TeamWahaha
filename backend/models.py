"""
Pydantic models for Lyra API request/response validation.

Keeps the FastAPI layer thin: these models define the HTTP contract
while src/api.py owns all business logic and data shapes.
"""

from typing import Any, Dict, List, Optional

from pydantic import BaseModel, Field


# ---------------------------------------------------------------------------
# Recommendation
# ---------------------------------------------------------------------------


class RecommendRequest(BaseModel):
    """POST /recommend request body."""

    user_input: str = Field(
        ...,
        min_length=1,
        max_length=2000,
        description="Free-form natural language input describing mood, situation, or listening needs",
        examples=["加班到凌晨，不想听太吵的歌"],
    )


class SongRecommendation(BaseModel):
    """A single song recommendation (mirrors Reranker output)."""

    title: str
    artist: str
    album: str = ""
    year: str = ""
    genre: str = ""
    reason: str = ""
    distance: float = 0.0


class IntentInfo(BaseModel):
    """Structured intent extracted by the Planner."""

    emotion: List[str] = []
    scene: List[str] = []
    listener_need: List[str] = []
    energy_level: str = "medium"
    avoid: List[str] = []
    free_text: str = ""


class TimingInfo(BaseModel):
    """Per-stage timing breakdown."""

    total_s: float
    planner_s: float = 0.0
    retriever_s: float = 0.0
    reranker_s: float = 0.0
    response_s: float = 0.0


class CacheInfo(BaseModel):
    """Reranker cache statistics."""

    size: int = 0
    hits: int = 0
    misses: int = 0
    max_size: int = 1000
    ttl_s: int = 1800


class MetadataInfo(BaseModel):
    """Pipeline metadata."""

    candidate_count: int
    result_count: int
    cache_info: Optional[CacheInfo] = None


class RecommendResponse(BaseModel):
    """POST /recommend response (success)."""

    success: bool = True
    module: str = "recommendation"
    query: str
    intent: IntentInfo
    recommendations: List[SongRecommendation]
    response: str
    timing: TimingInfo
    metadata: MetadataInfo


# ---------------------------------------------------------------------------
# Feedback
# ---------------------------------------------------------------------------


class FeedbackRequest(BaseModel):
    """POST /feedback request body."""

    user_query: str = Field(
        ...,
        min_length=1,
        description="The original user query this feedback refers to",
    )
    song_titles: List[str] = Field(
        ...,
        description="Song titles from the recommendation this feedback refers to",
    )
    ratings: Dict[str, str] = Field(
        default_factory=dict,
        description='Mapping of song title → "like" | "dislike" | "neutral"',
    )
    comment: Optional[str] = Field(
        None,
        description="Optional free-text comment from the user",
    )


class FeedbackResponse(BaseModel):
    """POST /feedback response."""

    success: bool = True
    module: str = "feedback"
    message: str = "Feedback recorded. Thank you!"


# ---------------------------------------------------------------------------
# Health
# ---------------------------------------------------------------------------


class HealthResponse(BaseModel):
    """GET /health response."""

    status: str = "ok"
    version: str = "1.0.0"
    modules: Dict[str, str] = Field(
        default_factory=lambda: {
            "recommendation": "stable",
            "recognition": "not_implemented",
            "composition": "not_implemented",
        }
    )


# ---------------------------------------------------------------------------
# Placeholder (future integration)
# ---------------------------------------------------------------------------


# ── Recognition ─────────────────────────────────────────────────────────


class RecognitionData(BaseModel):
    """Recognition result payload."""

    title: str = Field("", description="Recognised song title, empty if unknown")
    artist: str = Field("", description="Recognised artist, empty if unknown")
    confidence: float = Field(
        0.0, ge=0.0, le=1.0, description="Confidence score 0.0–1.0"
    )


class RecognitionResponse(BaseModel):
    """POST /recognition response envelope."""

    success: bool = True
    module: str = "recognition"
    data: RecognitionData = Field(default_factory=RecognitionData)
    message: str = "Recognition completed"


# ── Composition ─────────────────────────────────────────────────────────


class CompositionRequest(BaseModel):
    """POST /composition request body."""

    prompt: str = Field(
        ...,
        min_length=1,
        max_length=1000,
        description="Natural-language description of desired music",
        examples=["Create a relaxing piano melody"],
    )
    duration: int = Field(
        30,
        ge=1,
        le=300,
        description="Target duration in seconds (1–300)",
    )
    style: Optional[str] = Field(
        None,
        max_length=200,
        description="Optional musical style reference",
    )
    tempo: Optional[int] = Field(
        None,
        ge=20,
        le=300,
        description="Optional BPM hint",
    )
    key: Optional[str] = Field(
        None,
        max_length=30,
        description='Optional musical key hint (e.g. "C major")',
    )


class CompositionData(BaseModel):
    """Composition result payload."""

    audio_url: Optional[str] = Field(
        None, description="URL to generated audio file, null if not yet generated"
    )
    duration: int = Field(0, description="Actual duration in seconds")


class CompositionResponse(BaseModel):
    """POST /composition response envelope."""

    success: bool = True
    module: str = "composition"
    data: CompositionData = Field(default_factory=CompositionData)
    message: str = "Composition completed"


# ---------------------------------------------------------------------------
# Error
# ---------------------------------------------------------------------------


class ErrorResponse(BaseModel):
    """Standard error envelope returned on failures."""

    success: bool = False
    module: str = "backend"
    error: str
    detail: Optional[str] = None

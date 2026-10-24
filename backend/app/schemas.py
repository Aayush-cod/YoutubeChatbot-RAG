from typing import List, Literal, Optional

from pydantic import BaseModel, Field

# YouTube video IDs only contain letters, digits, "_" and "-".
VIDEO_ID_PATTERN = r"^[A-Za-z0-9_-]{5,32}$"


class Segment(BaseModel):
    """One caption line, same shape as the notebook's transcript_list items."""

    text: str
    start: float = Field(ge=0, description="Start time in seconds")
    duration: float = Field(default=0.0, ge=0)


class IngestRequest(BaseModel):
    video_id: str = Field(pattern=VIDEO_ID_PATTERN)
    segments: List[Segment] = Field(min_length=1, max_length=50_000)


class IngestResponse(BaseModel):
    video_id: str
    chunks: int
    cached: bool  # True if this video was already indexed


class SummaryRequest(BaseModel):
    video_id: str = Field(pattern=VIDEO_ID_PATTERN)


class KeyPoint(BaseModel):
    point: str = Field(description="One concise takeaway")
    timestamp_seconds: Optional[int] = Field(
        default=None, description="Approximate start time in seconds, if known"
    )


class VideoSummary(BaseModel):
    summary: str = Field(description="A 4-6 sentence overview of the video")
    key_points: List[KeyPoint] = Field(description="5-8 key takeaways")
    topics: List[str] = Field(description="3-8 short topic tags")


class ChatTurn(BaseModel):
    role: Literal["user", "assistant"]
    content: str


class ChatRequest(BaseModel):
    video_id: str = Field(pattern=VIDEO_ID_PATTERN)
    question: str = Field(min_length=1, max_length=1000)
    history: List[ChatTurn] = Field(default_factory=list, max_length=20)
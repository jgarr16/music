from __future__ import annotations

from enum import StrEnum
from typing import Any

from pydantic import BaseModel, Field


class MatchStatus(StrEnum):
    EXACT = "exact"
    PROBABLE = "probable"
    NOT_FOUND = "not_found"


class ParsedTrack(BaseModel):
    """Canonical record for one playlist row (music only)."""

    index: int = Field(description="0-based position in playlist XML order (includes gaps for skipped)")
    playlist_name: str
    artist: str
    title: str
    album: str = ""
    duration_ms: int | None = None
    kind: str = ""
    track_id: int | None = None
    original_fields: dict[str, Any] = Field(default_factory=dict)


class SearchQueries(BaseModel):
    artist_title: str
    title_artist: str
    title_only: str


class FreegalCandidate(BaseModel):
    title: str
    artist: str
    raw_text: str = ""


class MatchRow(BaseModel):
    """One row for matches.csv review."""

    source_index: int
    playlist_name: str
    source_artist: str
    source_title: str
    source_album: str
    query_used: str
    freegal_title: str = ""
    freegal_artist: str = ""
    confidence: float = 0.0
    status: MatchStatus = MatchStatus.NOT_FOUND
    all_queries_tried: str = ""


class SkippedTrack(BaseModel):
    index: int | None = None
    track_id: int | None = None
    reason: str
    detail: str = ""

from __future__ import annotations

import csv
import json
import logging
from pathlib import Path
from typing import Iterable

from app.models import MatchRow, MatchStatus, ParsedTrack, SkippedTrack

LOG = logging.getLogger(__name__)


PARSED_FIELDNAMES = [
    "index",
    "playlist_name",
    "artist",
    "title",
    "album",
    "duration_ms",
    "kind",
    "track_id",
    "search_artist_title",
    "search_title_artist",
    "search_title_only",
    "original_json",
]

MATCH_FIELDNAMES = [
    "source_index",
    "playlist_name",
    "source_artist",
    "source_title",
    "source_album",
    "query_used",
    "freegal_title",
    "freegal_artist",
    "confidence",
    "status",
    "all_queries_tried",
]


def write_parsed_tracks(path: Path, tracks: Iterable[ParsedTrack]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    rows = list(tracks)
    with path.open("w", newline="", encoding="utf-8") as f:
        w = csv.DictWriter(f, fieldnames=PARSED_FIELDNAMES)
        w.writeheader()
        for t in rows:
            w.writerow(
                {
                    "index": t.index,
                    "playlist_name": t.playlist_name,
                    "artist": t.artist,
                    "title": t.title,
                    "album": t.album,
                    "duration_ms": t.duration_ms if t.duration_ms is not None else "",
                    "kind": t.kind,
                    "track_id": t.track_id if t.track_id is not None else "",
                    "search_artist_title": t.original_fields.get("_search_artist_title", ""),
                    "search_title_artist": t.original_fields.get("_search_title_artist", ""),
                    "search_title_only": t.original_fields.get("_search_title_only", ""),
                    "original_json": json.dumps(t.original_fields, ensure_ascii=False, default=str),
                }
            )
    LOG.info("Wrote %s parsed tracks to %s", len(rows), path)


def read_parsed_tracks(path: Path) -> list[ParsedTrack]:
    out: list[ParsedTrack] = []
    with path.open(newline="", encoding="utf-8") as f:
        r = csv.DictReader(f)
        for row in r:
            orig = json.loads(row["original_json"])
            out.append(
                ParsedTrack(
                    index=int(row["index"]),
                    playlist_name=row["playlist_name"],
                    artist=row["artist"],
                    title=row["title"],
                    album=row.get("album") or "",
                    duration_ms=int(row["duration_ms"]) if row.get("duration_ms") not in (None, "") else None,
                    kind=row.get("kind") or "",
                    track_id=int(row["track_id"]) if row.get("track_id") not in (None, "") else None,
                    original_fields=orig,
                )
            )
    return out


def write_match_rows(path: Path, rows: Iterable[MatchRow]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    lst = list(rows)
    with path.open("w", newline="", encoding="utf-8") as f:
        w = csv.DictWriter(f, fieldnames=MATCH_FIELDNAMES)
        w.writeheader()
        for m in lst:
            w.writerow(
                {
                    "source_index": m.source_index,
                    "playlist_name": m.playlist_name,
                    "source_artist": m.source_artist,
                    "source_title": m.source_title,
                    "source_album": m.source_album,
                    "query_used": m.query_used,
                    "freegal_title": m.freegal_title,
                    "freegal_artist": m.freegal_artist,
                    "confidence": m.confidence,
                    "status": m.status.value,
                    "all_queries_tried": m.all_queries_tried,
                }
            )
    LOG.info("Wrote %s match rows to %s", len(lst), path)


def read_match_rows(path: Path) -> list[MatchRow]:
    out: list[MatchRow] = []
    with path.open(newline="", encoding="utf-8") as f:
        r = csv.DictReader(f)
        for row in r:
            out.append(
                MatchRow(
                    source_index=int(row["source_index"]),
                    playlist_name=row["playlist_name"],
                    source_artist=row["source_artist"],
                    source_title=row["source_title"],
                    source_album=row.get("source_album") or "",
                    query_used=row["query_used"],
                    freegal_title=row.get("freegal_title") or "",
                    freegal_artist=row.get("freegal_artist") or "",
                    confidence=float(row["confidence"]),
                    status=MatchStatus(row["status"]),
                    all_queries_tried=row.get("all_queries_tried") or "[]",
                )
            )
    return out


def write_skipped(path: Path, items: Iterable[SkippedTrack]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    lst = list(items)
    fieldnames = ["index", "track_id", "reason", "detail"]
    with path.open("w", newline="", encoding="utf-8") as f:
        w = csv.DictWriter(f, fieldnames=fieldnames)
        w.writeheader()
        for s in lst:
            w.writerow(
                {
                    "index": "" if s.index is None else s.index,
                    "track_id": "" if s.track_id is None else s.track_id,
                    "reason": s.reason,
                    "detail": s.detail,
                }
            )
    LOG.info("Wrote %s skipped rows to %s", len(lst), path)


def split_matches(rows: list[MatchRow]) -> tuple[list[MatchRow], list[MatchRow], list[MatchRow]]:
    matched = [r for r in rows if r.status == MatchStatus.EXACT]
    probable = [r for r in rows if r.status == MatchStatus.PROBABLE]
    unmatched = [r for r in rows if r.status == MatchStatus.NOT_FOUND]
    return matched, probable, unmatched

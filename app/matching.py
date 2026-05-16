from __future__ import annotations

import json
import logging
from dataclasses import dataclass

from rapidfuzz import fuzz

from app.config import AppConfig
from app.models import FreegalCandidate, MatchRow, MatchStatus, ParsedTrack
from app.normalize import normalize_for_matching

LOG = logging.getLogger(__name__)


@dataclass(frozen=True)
class ScoreResult:
    score: float
    candidate: FreegalCandidate | None


def score_track_against_candidate(
    source_artist: str,
    source_title: str,
    cand: FreegalCandidate,
    *,
    strip_noise: bool,
) -> float:
    """Weighted combination of token_set_ratio on artist+title pairs."""
    sa = normalize_for_matching(source_artist, strip_noise=strip_noise)
    st = normalize_for_matching(source_title, strip_noise=strip_noise)
    ca = normalize_for_matching(cand.artist, strip_noise=strip_noise)
    ct = normalize_for_matching(cand.title, strip_noise=strip_noise)

    s1 = fuzz.token_set_ratio(f"{sa} {st}", f"{ca} {ct}")
    s2 = fuzz.token_set_ratio(f"{st} {sa}", f"{ct} {ca}")
    s3 = fuzz.token_set_ratio(st, ct)
    s4 = fuzz.token_set_ratio(sa, ca) if sa and ca else 0
    combined = max(s1, s2)
    if ca:
        combined = max(combined, s3 * 0.95 + s4 * 0.05)
    else:
        combined = max(combined, s3)
    # UI often yields one blob of text; score against full row when title/artist split failed.
    if cand.raw_text:
        raw_n = normalize_for_matching(cand.raw_text, strip_noise=strip_noise)
        s5 = fuzz.token_set_ratio(f"{sa} {st}", raw_n)
        combined = max(combined, s5 * 0.98)
    return combined


def pick_best_candidate(
    track: ParsedTrack,
    candidates: list[FreegalCandidate],
    cfg: AppConfig,
) -> ScoreResult:
    strip = cfg.thresholds.strip_noise_terms
    if not candidates:
        return ScoreResult(0.0, None)

    best: FreegalCandidate | None = None
    best_score = -1.0
    for c in candidates[: cfg.thresholds.max_search_results]:
        sc = score_track_against_candidate(track.artist, track.title, c, strip_noise=strip)
        if sc > best_score:
            best_score = sc
            best = c
    return ScoreResult(best_score, best)


def classify_score(score: float, cfg: AppConfig) -> MatchStatus:
    if score >= cfg.thresholds.exact_min_score:
        return MatchStatus.EXACT
    if score >= cfg.thresholds.probable_min_score:
        return MatchStatus.PROBABLE
    return MatchStatus.NOT_FOUND


def primary_query_for_track(track: ParsedTrack, cfg: AppConfig) -> tuple[str, str]:
    """Returns (query_type, query_string)."""
    of = track.original_fields
    at = str(of.get("_search_artist_title", ""))
    ta = str(of.get("_search_title_artist", ""))
    to = str(of.get("_search_title_only", ""))
    order_map = {
        "artist_title": ("artist_title", at),
        "title_artist": ("title_artist", ta),
        "title_only": ("title_only", to),
    }
    key = cfg.thresholds.primary_query
    return order_map.get(key, ("artist_title", at))


def fallback_queries(track: ParsedTrack) -> list[tuple[str, str]]:
    of = track.original_fields
    return [
        ("artist_title", str(of.get("_search_artist_title", ""))),
        ("title_artist", str(of.get("_search_title_artist", ""))),
        ("title_only", str(of.get("_search_title_only", ""))),
    ]


def match_track_with_searcher(
    track: ParsedTrack,
    search_fn,
    cfg: AppConfig,
) -> MatchRow:
    """
    Try queries in order until candidates exist; pick best fuzzy score.
    search_fn(query: str) -> list[FreegalCandidate]
    """
    queries_tried: list[str] = []
    primary_type, primary_q = primary_query_for_track(track, cfg)
    ordered: list[tuple[str, str]] = []
    seen: set[str] = set()
    for qtype, qtext in [primary_query_for_track(track, cfg)] + [
        x for x in fallback_queries(track) if x[0] != primary_type
    ]:
        if not qtext.strip():
            continue
        key = f"{qtype}:{qtext}"
        if key in seen:
            continue
        seen.add(key)
        ordered.append((qtype, qtext))

    best_row: MatchRow | None = None
    for qtype, qtext in ordered:
        queries_tried.append(f"{qtype}={qtext}")
        try:
            cands = search_fn(qtext)
        except Exception as exc:  # noqa: BLE001
            LOG.warning("Search failed for %s: %s", qtext, exc)
            cands = []
        if not cands:
            continue
        sr = pick_best_candidate(track, cands, cfg)
        status = classify_score(sr.score, cfg)
        row = MatchRow(
            source_index=track.index,
            playlist_name=track.playlist_name,
            source_artist=track.artist,
            source_title=track.title,
            source_album=track.album,
            query_used=qtext,
            freegal_title=sr.candidate.title if sr.candidate else "",
            freegal_artist=sr.candidate.artist if sr.candidate else "",
            confidence=round(sr.score, 2),
            status=status,
            all_queries_tried=json.dumps(queries_tried),
        )
        if status == MatchStatus.EXACT:
            return row.model_copy(update={"all_queries_tried": json.dumps(queries_tried)})
        if best_row is None or sr.score > best_row.confidence:
            best_row = row

    if best_row is not None:
        return best_row.model_copy(update={"all_queries_tried": json.dumps(queries_tried)})

    return MatchRow(
        source_index=track.index,
        playlist_name=track.playlist_name,
        source_artist=track.artist,
        source_title=track.title,
        source_album=track.album,
        query_used=ordered[0][1] if ordered else "",
        confidence=0.0,
        status=MatchStatus.NOT_FOUND,
        all_queries_tried=json.dumps(queries_tried),
    )

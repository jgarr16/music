from __future__ import annotations

import logging
import plistlib
import re
from pathlib import Path
from typing import Any

from app.models import ParsedTrack, SkippedTrack
from app.normalize import build_queries, is_music_kind

LOG = logging.getLogger(__name__)


def _strip_plist_doctype(raw: bytes) -> bytes:
    """plistlib rejects some DOCTYPE lines; strip the first plist DOCTYPE."""
    return re.sub(br"<!DOCTYPE\s+plist[^>]*>", b"", raw, count=1, flags=re.IGNORECASE)


def load_plist(path: Path) -> dict[str, Any]:
    raw = path.read_bytes()
    try:
        return plistlib.loads(raw)
    except Exception:
        LOG.debug("plistlib failed on raw file, retrying without DOCTYPE")
        return plistlib.loads(_strip_plist_doctype(raw))


def _track_dict(root: dict[str, Any]) -> dict[int, dict[str, Any]]:
    tracks = root.get("Tracks") or {}
    out: dict[int, dict[str, Any]] = {}
    if not isinstance(tracks, dict):
        return out
    for _k, v in tracks.items():
        if isinstance(v, dict) and "Track ID" in v:
            tid = int(v["Track ID"])
            out[tid] = v
    return out


def _playlist_entries(root: dict[str, Any]) -> list[dict[str, Any]]:
    pl = root.get("Playlists")
    if not isinstance(pl, list):
        return []
    return [p for p in pl if isinstance(p, dict)]


def list_playlist_names(root: dict[str, Any]) -> list[str]:
    names: list[str] = []
    for p in _playlist_entries(root):
        if p.get("Folder"):
            continue
        if "Playlist Items" not in p:
            continue
        n = p.get("Name")
        if isinstance(n, str):
            names.append(n)
    return sorted(set(names))


def select_playlist(root: dict[str, Any], playlist_name: str | None) -> dict[str, Any]:
    entries = _playlist_entries(root)
    candidates: list[dict[str, Any]] = []
    for p in entries:
        if p.get("Folder"):
            continue
        if "Playlist Items" not in p:
            continue
        if p.get("Master"):
            continue
        candidates.append(p)

    if not candidates:
        raise ValueError("No playlists with 'Playlist Items' found in XML.")

    if playlist_name:
        for p in candidates:
            if p.get("Name") == playlist_name:
                return p
        raise ValueError(f"Playlist named {playlist_name!r} not found. Available: {list_playlist_names(root)}")

    if len(candidates) == 1:
        return candidates[0]

    names = [str(p.get("Name", "?")) for p in candidates]
    raise ValueError(
        "Multiple playlists found; pass --playlist-name. Options: " + ", ".join(names[:50])
        + (" …" if len(names) > 50 else "")
    )


def parse_playlist_xml(
    path: Path,
    *,
    playlist_name: str | None = None,
    strip_noise: bool = True,
) -> tuple[list[ParsedTrack], list[SkippedTrack]]:
    root = load_plist(path)
    playlist = select_playlist(root, playlist_name)
    pname = str(playlist.get("Name", ""))
    items = playlist.get("Playlist Items") or []
    if not isinstance(items, list):
        items = []

    tracks_by_id = _track_dict(root)
    parsed: list[ParsedTrack] = []
    skipped: list[SkippedTrack] = []

    for idx, row in enumerate(items):
        if not isinstance(row, dict):
            skipped.append(SkippedTrack(index=idx, reason="invalid_row", detail="not a dict"))
            continue
        tid = row.get("Track ID")
        if tid is None:
            skipped.append(SkippedTrack(index=idx, reason="missing_track_id", detail=""))
            continue
        tid_int = int(tid)
        meta = tracks_by_id.get(tid_int)
        if not meta:
            skipped.append(SkippedTrack(index=idx, track_id=tid_int, reason="track_not_in_library", detail=""))
            continue

        kind = str(meta.get("Kind") or "")
        if not is_music_kind(kind):
            skipped.append(
                SkippedTrack(
                    index=idx,
                    track_id=tid_int,
                    reason="non_music_kind",
                    detail=kind,
                )
            )
            continue

        title = str(meta.get("Name") or "").strip()
        artist = str(meta.get("Artist") or meta.get("Album Artist") or "").strip()
        if not title and not artist:
            skipped.append(SkippedTrack(index=idx, track_id=tid_int, reason="missing_title_and_artist", detail=kind))
            continue

        album = str(meta.get("Album") or "")
        total_time = meta.get("Total Time")
        duration_ms = int(total_time) if total_time is not None else None

        at, ta, to = build_queries(artist, title, strip_noise=strip_noise)

        original = {k: meta[k] for k in sorted(meta.keys())}
        original["_search_artist_title"] = at
        original["_search_title_artist"] = ta
        original["_search_title_only"] = to

        parsed.append(
            ParsedTrack(
                index=idx,
                playlist_name=pname,
                artist=artist,
                title=title,
                album=album,
                duration_ms=duration_ms,
                kind=kind,
                track_id=tid_int,
                original_fields=original,
            )
        )

    return parsed, skipped

"""End-to-end: parse fixture XML, mock Freegal search, write match classification."""

from __future__ import annotations

from pathlib import Path

from app.config import AppConfig
from app.matching import match_track_with_searcher
from app.models import FreegalCandidate, MatchStatus
from app.report import read_parsed_tracks, write_parsed_tracks, write_match_rows
from app.xml_parser import parse_playlist_xml

FIXTURE = Path(__file__).parent / "fixtures" / "minimal_library.xml"


def test_parse_and_match_with_mock_search(tmp_path: Path) -> None:
    tracks, _skipped = parse_playlist_xml(FIXTURE, playlist_name="Test Mix")
    parsed_path = tmp_path / "parsed_tracks.csv"
    write_parsed_tracks(parsed_path, tracks)

    loaded = read_parsed_tracks(parsed_path)
    cfg = AppConfig.load()

    def mock_search(q: str) -> list[FreegalCandidate]:
        ql = q.lower()
        if "barracuda" in ql and "heart" in ql:
            return [FreegalCandidate(title="Barracuda", artist="Heart")]
        return []

    rows = [match_track_with_searcher(t, mock_search, cfg) for t in loaded]
    assert rows[0].status == MatchStatus.EXACT
    matches_path = tmp_path / "matches.csv"
    write_match_rows(matches_path, rows)
    assert matches_path.read_text().count("exact") >= 1


def test_freegal_bot_mocked(monkeypatch) -> None:
    """Ensure automation entrypoint can be patched in tests."""
    from app import freegal_bot
    from app.config import AppConfig

    called: list[str] = []

    def fake_run(cfg, fn):
        called.append("run")

    monkeypatch.setattr(freegal_bot, "run_browser_session", fake_run)
    freegal_bot.run_browser_session(AppConfig.load(), lambda b: None)
    assert called == ["run"]

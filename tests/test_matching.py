from app.config import AppConfig
from app.matching import classify_score, pick_best_candidate, score_track_against_candidate
from app.models import FreegalCandidate, ParsedTrack


def test_score_identical_high() -> None:
    cfg = AppConfig.load()
    c = FreegalCandidate(title="Barracuda", artist="Heart")
    sc = score_track_against_candidate("Heart", "Barracuda", c, strip_noise=cfg.thresholds.strip_noise_terms)
    assert sc >= 90


def test_pick_best_among_candidates() -> None:
    cfg = AppConfig.load()
    t = ParsedTrack(
        index=0,
        playlist_name="P",
        artist="Heart",
        title="Barracuda",
        original_fields={"_search_artist_title": "Heart Barracuda", "_search_title_artist": "Barracuda Heart", "_search_title_only": "Barracuda"},
    )
    cands = [
        FreegalCandidate(title="Wrong", artist="Other"),
        FreegalCandidate(title="Barracuda", artist="Heart"),
    ]
    sr = pick_best_candidate(t, cands, cfg)
    assert sr.candidate is not None
    assert sr.candidate.artist == "Heart"


def test_classify_thresholds() -> None:
    cfg = AppConfig.load()
    assert classify_score(95, cfg).value == "exact"
    assert classify_score(80, cfg).value == "probable"
    assert classify_score(10, cfg).value == "not_found"

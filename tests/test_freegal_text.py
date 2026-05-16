from app.freegal_bot import _lines_from_block, _title_artist_from_row
from app.matching import score_track_against_candidate
from app.models import FreegalCandidate
from app.config import AppConfig


def test_lines_from_block_skips_play_noise() -> None:
    raw = "Play\nSomebody That I Used to Know\nGotye"
    lines = _lines_from_block(raw)
    assert "Somebody" in lines[0]


def test_title_artist_from_row_two_lines() -> None:
    t, a = _title_artist_from_row("Barracuda\nHeart", "q")
    assert "Barracuda" in t
    assert "Heart" in a


def test_score_boosted_by_raw_text_blob() -> None:
    cfg = AppConfig.load()
    c = FreegalCandidate(
        title="",
        artist="",
        raw_text="Somebody That I Used to Know\nGotye\nDownload",
    )
    sc = score_track_against_candidate(
        "Gotye",
        "Somebody That I Used to Know (feat. Kimbra)",
        c,
        strip_noise=cfg.thresholds.strip_noise_terms,
    )
    assert sc >= 70

import pytest

from app.normalize import build_queries, is_music_kind, normalize_for_matching, strip_noise_terms


@pytest.mark.parametrize(
    "raw,expected_substrings",
    [
        ("The Beatles — Help!", "help"),
        ("Oops!... I Did It Again", "oops i did it again"),
    ],
)
def test_normalize_lowercase_no_punct(raw: str, expected_substrings: str) -> None:
    n = normalize_for_matching(raw, strip_noise=False)
    assert expected_substrings in n


def test_strip_noise_removes_feat() -> None:
    t = strip_noise_terms("Hello feat. Guest Vocalist", enabled=True)
    assert "guest" not in t.lower()


def test_build_queries_order() -> None:
    at, ta, to = build_queries("Heart", "Barracuda", strip_noise=True)
    assert "heart" in at.lower()
    assert "barracuda" in at.lower()
    assert to.lower() == "barracuda"


def test_non_music_kind() -> None:
    assert is_music_kind("Apple Music AAC audio file") is True
    assert is_music_kind("MPEG-4 podcast") is False

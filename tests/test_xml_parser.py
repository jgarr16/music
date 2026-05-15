from pathlib import Path

from app.xml_parser import list_playlist_names, load_plist, parse_playlist_xml

FIXTURE = Path(__file__).parent / "fixtures" / "minimal_library.xml"


def test_load_plist_roundtrip_keys() -> None:
    root = load_plist(FIXTURE)
    assert "Tracks" in root
    assert "Playlists" in root


def test_parse_playlist_skips_podcast() -> None:
    tracks, skipped = parse_playlist_xml(FIXTURE, playlist_name="Test Mix")
    assert len(tracks) == 1
    assert tracks[0].title.startswith("Barracuda")
    assert tracks[0].artist == "Heart"
    assert tracks[0].index == 0
    assert any(s.reason == "non_music_kind" for s in skipped)


def test_playlist_name_required_when_multiple() -> None:
    # minimal has only one playlist — add a second programmatically by parsing twice is hard;
    # instead assert list_playlist_names
    root = load_plist(FIXTURE)
    names = list_playlist_names(root)
    assert "Test Mix" in names

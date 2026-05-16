from __future__ import annotations

from pathlib import Path

from click.testing import CliRunner

from app.cli import main
from app.models import ParsedTrack
from app.report import read_match_rows, write_parsed_tracks


def test_match_offline_respects_limit(tmp_path: Path) -> None:
    inp = tmp_path / "parsed_tracks.csv"
    out = tmp_path / "out"
    tracks = [
        ParsedTrack(
            index=i,
            playlist_name="P",
            artist="Artist",
            title=f"Title{i}",
            original_fields={
                "_search_artist_title": f"Artist Title{i}",
                "_search_title_artist": f"Title{i} Artist",
                "_search_title_only": f"Title{i}",
            },
        )
        for i in range(5)
    ]
    write_parsed_tracks(inp, tracks)

    runner = CliRunner()
    result = runner.invoke(
        main,
        ["match", "--input", str(inp), "--out", str(out), "--offline", "--limit", "2"],
        catch_exceptions=False,
    )
    assert result.exit_code == 0
    rows = read_match_rows(out / "matches.csv")
    assert len(rows) == 2
    assert "subset" in result.output.lower() or "first 2" in result.output

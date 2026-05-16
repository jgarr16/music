from __future__ import annotations

import logging
import sys
from pathlib import Path

import click

from app import __version__
from app.config import AppConfig
from app.freegal_bot import FreegalBot, make_search_fn, run_browser_session
from app.matching import match_track_with_searcher
from app.report import (
    read_match_rows,
    read_parsed_tracks,
    split_matches,
    write_match_rows,
    write_parsed_tracks,
    write_skipped,
)
from app.xml_parser import parse_playlist_xml

LOG = logging.getLogger(__name__)


def _setup_logging(verbose: bool) -> None:
    level = logging.DEBUG if verbose else logging.INFO
    logging.basicConfig(
        level=level,
        format="%(levelname)s %(name)s: %(message)s",
        stream=sys.stderr,
    )


def _load_cfg(config: Path | None) -> AppConfig:
    return AppConfig.load(config)


@click.group()
@click.version_option(__version__)
@click.option("-v", "--verbose", is_flag=True)
@click.pass_context
def main(ctx: click.Context, verbose: bool) -> None:
    """Apple Music playlist XML → Freegal matching and playlist helper."""
    ctx.ensure_object(dict)
    ctx.obj["verbose"] = verbose
    _setup_logging(verbose)


@main.command("parse")
@click.option("--input", "input_path", type=click.Path(exists=True, path_type=Path), required=True)
@click.option("--out", "out_dir", type=click.Path(path_type=Path), required=True)
@click.option("--playlist-name", default=None, help="Playlist Name value when multiple playlists exist in XML.")
@click.option("--config", type=click.Path(path_type=Path), default=None)
@click.pass_context
def cmd_parse(ctx: click.Context, input_path: Path, out_dir: Path, playlist_name: str | None, config: Path | None) -> None:
    """Parse iTunes/Music plist XML and write parsed_tracks.csv + skipped_tracks.csv."""
    cfg = _load_cfg(config)
    tracks, skipped = parse_playlist_xml(
        input_path,
        playlist_name=playlist_name,
        strip_noise=cfg.thresholds.strip_noise_terms,
    )
    out_dir.mkdir(parents=True, exist_ok=True)
    write_parsed_tracks(out_dir / "parsed_tracks.csv", tracks)
    write_skipped(out_dir / "skipped_tracks.csv", skipped)
    print(
        f"\nParse complete.\n"
        f"  Playlist tracks (music): {len(tracks)}\n"
        f"  Skipped rows: {len(skipped)}\n"
        f"  Output: {out_dir / 'parsed_tracks.csv'}\n"
    )


@main.command("match")
@click.option("--input", "input_path", type=click.Path(exists=True, path_type=Path), required=True)
@click.option("--out", "out_dir", type=click.Path(path_type=Path), required=True)
@click.option("--config", type=click.Path(path_type=Path), default=None)
@click.option(
    "--offline",
    is_flag=True,
    help="Do not open a browser; every search returns no hits (for CI / tests).",
)
@click.option(
    "--limit",
    type=click.IntRange(min=1),
    default=None,
    help="Only process the first N tracks after sorting by playlist index (smoke tests).",
)
@click.pass_context
def cmd_match(
    ctx: click.Context,
    input_path: Path,
    out_dir: Path,
    config: Path | None,
    offline: bool,
    limit: int | None,
) -> None:
    """Search Freegal per track, fuzzy-score results, write matches.csv and unmatched_tracks.csv."""
    cfg = _load_cfg(config)
    all_tracks = sorted(read_parsed_tracks(input_path), key=lambda t: t.index)
    total_in_file = len(all_tracks)
    tracks = all_tracks[:limit] if limit is not None else all_tracks
    out_dir.mkdir(parents=True, exist_ok=True)
    rows: list = []

    if offline:

        def search_fn(_q: str):
            return []

        for t in tracks:
            rows.append(match_track_with_searcher(t, search_fn, cfg))
    else:

        def session(bot: FreegalBot) -> None:
            bot.goto_home()
            bot.wait_for_manual_login()
            sf = make_search_fn(bot)
            for t in tracks:
                LOG.info("Matching track %s: %s — %s", t.index, t.artist, t.title)
                rows.append(match_track_with_searcher(t, sf, cfg))

        run_browser_session(cfg, session)

    write_match_rows(out_dir / "matches.csv", rows)
    _, _, unmatched = split_matches(rows)
    write_match_rows(out_dir / "unmatched_tracks.csv", unmatched)
    exact, probable, nf = split_matches(rows)
    limit_note = ""
    if limit is not None:
        limit_note = f"  (subset: first {len(rows)} of {total_in_file} rows in input, --limit {limit})\n"
    print(
        f"\nMatch complete.\n"
        f"{limit_note}"
        f"  Total processed: {len(rows)}\n"
        f"  Exact: {len(exact)}\n"
        f"  Probable: {len(probable)}\n"
        f"  Not found: {len(nf)}\n"
        f"  matches.csv → {out_dir / 'matches.csv'}\n"
    )


@main.command("freegal-sync")
@click.option("--input", "input_path", type=click.Path(exists=True, path_type=Path), required=True)
@click.option("--playlist", "playlist_name", required=True, help="Target Freegal playlist name to add into.")
@click.option("--out", "out_dir", type=click.Path(path_type=Path), default=None, help="Directory for sync logs / screenshots.")
@click.option("--config", type=click.Path(path_type=Path), default=None)
@click.option("--dry-run", "dry_run", is_flag=True, help="Log actions only; do not click Freegal UI.")
@click.option(
    "--apply",
    "apply_mode",
    is_flag=True,
    help="Perform add-to-playlist actions (still opens browser unless --dry-run).",
)
@click.option(
    "--approve-probable",
    is_flag=True,
    help="Include probable matches as well as exact matches.",
)
@click.option(
    "--confirm-probable",
    is_flag=True,
    help="If set with --apply and --approve-probable, prompt before each probable row.",
)
@click.pass_context
def cmd_freegal_sync(
    ctx: click.Context,
    input_path: Path,
    playlist_name: str,
    out_dir: Path | None,
    config: Path | None,
    dry_run: bool,
    apply_mode: bool,
    approve_probable: bool,
    confirm_probable: bool,
) -> None:
    """Use Playwright to add matched rows to a Freegal playlist."""
    if not dry_run and not apply_mode:
        raise click.UsageError("Pass either --dry-run or --apply.")

    cfg = _load_cfg(config)
    rows = read_match_rows(input_path)
    base = out_dir or input_path.parent
    base.mkdir(parents=True, exist_ok=True)

    from app.models import MatchStatus, SkippedTrack

    to_process = [r for r in rows if r.status == MatchStatus.EXACT]
    skipped: list[SkippedTrack] = []
    if approve_probable:
        probable = [r for r in rows if r.status == MatchStatus.PROBABLE]
        if confirm_probable and apply_mode and not dry_run:
            kept: list = []
            for r in probable:
                ans = input(f"Add probable match {r.source_artist} — {r.source_title}? [y/N] ")
                if ans.strip().lower() == "y":
                    kept.append(r)
                else:
                    skipped.append(
                        SkippedTrack(
                            index=r.source_index,
                            reason="probable_declined_interactive",
                            detail=f"{r.freegal_artist} — {r.freegal_title}",
                        )
                    )
            to_process.extend(kept)
        else:
            to_process.extend(probable)
    else:
        for r in rows:
            if r.status == MatchStatus.PROBABLE:
                skipped.append(
                    SkippedTrack(
                        index=r.source_index,
                        reason="probable_not_approved",
                        detail="Re-run with --approve-probable or edit matches.csv status to exact.",
                    )
                )

    for r in rows:
        if r.status == MatchStatus.NOT_FOUND:
            skipped.append(
                SkippedTrack(
                    index=r.source_index,
                    reason="not_matched",
                    detail=f"{r.source_artist} — {r.source_title}",
                )
            )

    added = 0
    failed = 0

    if dry_run:
        for r in to_process:
            LOG.info(
                "[dry-run] Would sync to playlist %r: %s — %s (Freegal: %s — %s, status=%s)",
                playlist_name,
                r.source_artist,
                r.source_title,
                r.freegal_artist,
                r.freegal_title,
                r.status.value,
            )
        added = len(to_process)
    else:

        def sync_session(bot: FreegalBot) -> None:
            nonlocal added, failed
            bot.goto_home()
            bot.wait_for_manual_login()
            for r in to_process:
                try:
                    bot.add_match_to_playlist(r, playlist_name, dry_run=not apply_mode)
                    added += 1
                except Exception as exc:  # noqa: BLE001
                    LOG.exception("Failed row: %s", r)
                    failed += 1
                    skipped.append(
                        SkippedTrack(
                            index=r.source_index,
                            reason="automation_error",
                            detail=str(exc),
                        )
                    )

        run_browser_session(cfg, sync_session)
    write_skipped(base / "sync_skipped.csv", skipped)
    print(
        f"\nFreegal sync summary\n"
        f"  Total in CSV: {len(rows)}\n"
        f"  Queued for playlist: {len(to_process)}\n"
        f"  Added / attempted OK: {added}\n"
        f"  Failed: {failed}\n"
        f"  Skipped / declined rows logged: {len(skipped)} → {base / 'sync_skipped.csv'}\n"
    )


if __name__ == "__main__":
    main()

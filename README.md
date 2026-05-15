# Apple Music → Freegal playlist helper

This repository contains a **CLI-first Python tool** that reads a **Music / iTunes playlist export (XML plist)**—metadata only, no Apple Music audio download—and helps you **recreate the same sequence on [Freegal](https://freegalmusic.com)** using **browser automation** (Playwright). It does **not** scrape or download subscription audio from Apple.

## Legal / intent

- The tool processes **playlist metadata you already exported** from the Apple Music app (track names, artists, album titles, durations, etc.).
- **Freegal** interaction is performed through a **real browser session** under your control, similar to how you would click the site yourself. There is **no reliance on a documented Freegal public API**.
- You are responsible for complying with Apple’s and your library’s terms of service.

## Requirements

- **Python 3.12+** (3.12 is the reference version; newer 3.x generally works).
- macOS-friendly paths; runs locally (**no server**).
- [Playwright](https://playwright.dev/python/) browsers: after install, run `playwright install chromium`.

## Setup

```bash
cd music
python3.12 -m venv .venv
source .venv/bin/activate
pip install -e ".[dev]"
playwright install chromium
```

Optional: copy `.env.example` to `.env` and adjust `MUSIC_FREEGAL_*` variables (see [pydantic-settings](https://docs.pydantic.dev/latest/concepts/pydantic_settings/) nested env rules).

## Configuration

Thresholds, query order, and Playwright timeouts live in **`config/default.toml`**. You can point to another file by extending the CLI later; today the defaults load from that path relative to the repo root.

## Workflow

### 1. Parse Apple XML → `parsed_tracks.csv`

```bash
python -m app parse --input /path/to/playlist.xml --out output/
```

If the file contains **multiple playlists**, pass the playlist’s **Name** field:

```bash
python -m app parse --input library.xml --out output/ --playlist-name "Ace"
```

Outputs:

- `output/parsed_tracks.csv` — normalized tracks + search query columns  
- `output/skipped_tracks.csv` — non-music rows, missing metadata, etc., with **human-readable reasons**

### 2. Match against Freegal search → `matches.csv`

Opens Chromium (headed by default), navigates to Freegal, then **pauses for you to log in** at the terminal. For each track it runs catalog search, collects candidate titles/artists, and **fuzzy-scores** the best hit.

```bash
python -m app match --input output/parsed_tracks.csv --out output/
```

**Offline / CI (no browser, no hits):**

```bash
python -m app match --input output/parsed_tracks.csv --out output/ --offline
```

Outputs:

- `output/matches.csv` — source row, query used, best Freegal hit, confidence, status (`exact` / `probable` / `not_found`)  
- `output/unmatched_tracks.csv` — rows with `not_found` only

### 3. Sync to a Freegal playlist

**Dry-run** (no browser; prints what would be queued):

```bash
python -m app freegal-sync --input output/matches.csv --playlist "My Freegal Playlist" --dry-run
```

**Apply** (opens browser, login pause, then attempts UI automation):

```bash
python -m app freegal-sync --input output/matches.csv --playlist "My Freegal Playlist" --apply
```

- By default only **`exact`** matches are queued. Add **`--approve-probable`** to include fuzzy **`probable`** rows.  
- **`--confirm-probable`** (with `--apply` and `--approve-probable`) prompts **y/N** per probable row.  
- Rows that are not matched, declined, or fail automation are logged to **`sync_skipped.csv`** in the output directory (defaults next to the input CSV).

> **Note:** The “add to playlist” portion of automation is a **skeleton** with **TODO selectors** (`app/selectors.py`). You will almost certainly need to adjust selectors for your library’s Freegal theme.

## Updating Freegal selectors

1. Run `python -m app match ...` or `freegal-sync --apply` with `headless = false` in `config/default.toml`.  
2. Open DevTools, inspect the **search box**, **result list items**, and **add-to-playlist** controls.  
3. Edit **`app/selectors.py`** (`FreegalSelectors`) with stable CSS or text-based `locator` strategies.  
4. Prefer attributes like `[data-testid=...]` when available; avoid long positional `nth()` chains.  
5. On errors, the bot saves screenshots under **`output/screenshots/`**.

## Tests

```bash
pytest
```

Includes unit tests for XML parsing, normalization, fuzzy ranking, a small **integration** parse+match path with a **mocked** search function, and a **mocked** `run_browser_session` hook.

## Sample CSVs

See **`output/sample_parsed_tracks.csv`** and **`output/sample_matches.csv`** for column shapes.

## Troubleshooting

| Symptom | What to try |
|--------|-------------|
| `plistlib` errors on export | Re-export from Music; ensure file is UTF-8 XML plist. The parser strips a common DOCTYPE if needed. |
| “Multiple playlists found” | Pass `--playlist-name` matching the `<key>Name</key>` string in the XML. |
| No Freegal search hits parsed | Selectors in `selectors.py` do not match your site skin—update them. |
| Playwright timeout | Increase `navigation_timeout_ms` / `action_timeout_ms` in `config/default.toml`. |

## Project layout

- `app/xml_parser.py` — Apple plist playlist + track dictionary resolution  
- `app/normalize.py` — string cleanup + query building  
- `app/matching.py` — rapidfuzz scoring + status thresholds  
- `app/freegal_bot.py` — Playwright session, login pause, search / add skeleton  
- `app/selectors.py` — **single place** for DOM selectors  
- `app/report.py` — CSV readers/writers  
- `tests/fixtures/minimal_library.xml` — tiny library for tests  

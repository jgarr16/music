"""
Centralized CSS / text selectors for Freegal.

The site varies by library consortium and A/B tests. When automation breaks,
update these strings to match the current DOM (use browser devtools).

TODO: verify each selector against your library's Freegal skin after deploy.
"""

from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True)
class FreegalSelectors:
    # Global search field on homepage or catalog
    search_input: str = 'input[placeholder*="Search" i], input[type="search"], #search'

    # Container listing search hits (adjust to a stable parent of result cards)
    search_results_container: str = ".search-results, [class*='result'], main"

    # Each individual result row/card — prefer data-testid if present
    search_result_item: str = "[class*='result-item'], li.search-result, .track-row"

    # Title / artist within a result item
    result_title: str = ".title, [class*='track-title'], h3, h4"
    result_artist: str = ".artist, [class*='track-artist'], .subtitle"

    # Add-to-playlist flow (highly site-specific — placeholders)
    add_to_playlist_button: str = 'button:has-text("Add to playlist"), [aria-label*="playlist" i]'
    playlist_name_input: str = 'input[name*="playlist" i], input[placeholder*="playlist" i]'
    playlist_confirm: str = 'button:has-text("Save"), button:has-text("Add")'

    # Heuristic: element that only appears when logged in (library card, avatar, etc.)
    logged_in_marker: str = '[class*="user"], [class*="account"], a[href*="logout" i]'


SELECTORS = FreegalSelectors()

# Tried in order after `search_result_item` if no sane hit count (see freegal_bot).
SEARCH_RESULT_ROW_FALLBACKS: tuple[str, ...] = (
    "[class*='search-result']",
    "[class*='SearchResult']",
    "[class*='song'][class*='row']",
    "[class*='track'][class*='row']",
    "[class*='media'][class*='item']",
    "mat-list-item",
    "tbody tr",
    "table[role='grid'] tr",
    "article",
    "[data-cy*='result']",
    "[data-testid*='result']",
)

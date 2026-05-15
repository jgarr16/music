from __future__ import annotations

import logging
import re
import time
from pathlib import Path
from typing import Callable

from playwright.sync_api import Page, TimeoutError as PlaywrightTimeoutError, sync_playwright

from app.config import AppConfig
from app.models import FreegalCandidate, MatchRow
from app.selectors import SELECTORS

LOG = logging.getLogger(__name__)


def _screenshot_dir() -> Path:
    p = Path(__file__).resolve().parent.parent / "output" / "screenshots"
    p.mkdir(parents=True, exist_ok=True)
    return p


def _safe_name(s: str) -> str:
    return re.sub(r"[^\w\-]+", "_", s)[:80]


class FreegalBot:
    """Playwright automation for Freegal search + playlist actions (best-effort)."""

    def __init__(self, page: Page, cfg: AppConfig) -> None:
        self.page = page
        self.cfg = cfg
        self._pw_cfg = cfg.playwright

    def goto_home(self) -> None:
        url = self._pw_cfg.freegal_base_url.rstrip("/")
        LOG.info("Navigating to %s", url)
        self.page.goto(url, timeout=self._pw_cfg.navigation_timeout_ms)

    def wait_for_manual_login(self) -> None:
        LOG.info(
            "Waiting for you to complete library login in the browser (timeout %ss).",
            self._pw_cfg.login_wait_timeout_sec,
        )
        print(
            "\n>>> Open Freegal and log in through your library if prompted.\n"
            ">>> When the catalog is ready, return to this terminal and press Enter.\n"
        )
        import sys

        if sys.stdin.isatty():
            input(">>> Press Enter when logged in… ")
        else:
            time.sleep(min(30, self._pw_cfg.post_login_settle_sec))
            LOG.warning("Non-interactive stdin: continuing after brief settle delay.")
        time.sleep(self._pw_cfg.post_login_settle_sec)

    def search_tracks(self, query: str) -> list[FreegalCandidate]:
        """Run a catalog search and parse visible results (selector-dependent)."""
        if not query.strip():
            return []
        sel = SELECTORS
        try:
            box = self.page.locator(sel.search_input).first
            box.click(timeout=self._pw_cfg.action_timeout_ms)
            box.fill("")
            box.fill(query)
            box.press("Enter")
            self.page.wait_for_timeout(800)
            items = self.page.locator(sel.search_result_item)
            n = items.count()
            if n == 0:
                LOG.warning("No search results parsed (selectors may need updating). query=%r", query)
                return []
            out: list[FreegalCandidate] = []
            for i in range(min(n, self.cfg.thresholds.max_search_results)):
                el = items.nth(i)
                title = ""
                artist = ""
                try:
                    tloc = el.locator(sel.result_title).first
                    if tloc.count():
                        title = tloc.inner_text(timeout=2000).strip()
                except PlaywrightTimeoutError:
                    pass
                try:
                    aloc = el.locator(sel.result_artist).first
                    if aloc.count():
                        artist = aloc.inner_text(timeout=2000).strip()
                except PlaywrightTimeoutError:
                    pass
                raw = ""
                try:
                    raw = el.inner_text(timeout=2000).strip()
                except PlaywrightTimeoutError:
                    pass
                if not title and raw:
                    title = raw.split("\n")[0][:200]
                out.append(FreegalCandidate(title=title or query, artist=artist, raw_text=raw))
            return out
        except Exception as exc:  # noqa: BLE001
            LOG.exception("Freegal search failed: %s", exc)
            path = _screenshot_dir() / f"error_search_{_safe_name(query)}.png"
            try:
                self.page.screenshot(path=str(path), full_page=True)
                LOG.error("Saved screenshot to %s", path)
            except Exception:
                pass
            return []

    def add_match_to_playlist(self, row: MatchRow, playlist_name: str, *, dry_run: bool) -> None:
        """Re-search using stored query and attempt add-to-playlist UI flow."""
        if dry_run:
            LOG.info(
                "[dry-run] Would add to playlist %r: %s — %s (query=%r)",
                playlist_name,
                row.freegal_artist,
                row.freegal_title,
                row.query_used,
            )
            return
        self.search_tracks(row.query_used)
        # TODO: click the matching result, open add-to-playlist, select playlist_name
        try:
            self.page.locator(SELECTORS.add_to_playlist_button).first.click(timeout=self._pw_cfg.action_timeout_ms)
        except Exception as exc:  # noqa: BLE001
            path = _screenshot_dir() / f"error_add_{_safe_name(row.query_used)}.png"
            self.page.screenshot(path=str(path), full_page=True)
            LOG.error("Add-to-playlist UI not completed (%s); screenshot %s", exc, path)
            raise


def run_browser_session(
    cfg: AppConfig,
    fn: Callable[[FreegalBot], None],
) -> None:
    """Start Playwright, run callback with FreegalBot, always close browser."""
    with sync_playwright() as p:
        browser = p.chromium.launch(headless=cfg.playwright.headless)
        try:
            page = browser.new_page()
            bot = FreegalBot(page, cfg)
            fn(bot)
        finally:
            browser.close()


def make_search_fn(bot: FreegalBot) -> Callable[[str], list[FreegalCandidate]]:
    return bot.search_tracks

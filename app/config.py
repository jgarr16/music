from __future__ import annotations

import logging
from pathlib import Path
from typing import Any

from pydantic import BaseModel, Field
from pydantic_settings import BaseSettings, SettingsConfigDict

LOG = logging.getLogger(__name__)

ROOT = Path(__file__).resolve().parent.parent
DEFAULT_CONFIG_PATH = ROOT / "config" / "default.toml"


class ThresholdConfig(BaseModel):
    exact_min_score: float = 92.0
    probable_min_score: float = 78.0
    max_search_results: int = 12
    primary_query: str = "artist_title"
    strip_noise_terms: bool = True


class PlaywrightConfig(BaseModel):
    freegal_base_url: str = "https://freegalmusic.com"
    headless: bool = False
    login_wait_timeout_sec: int = 600
    navigation_timeout_ms: int = 45000
    action_timeout_ms: int = 20000
    post_login_settle_sec: int = 3
    # Total wall time (ms) for all result-row selector attempts after one search submit.
    search_results_wait_ms: int = 6000
    search_results_poll_ms: int = 400
    # If a selector matches more than this many nodes, treat it as too broad and try next.
    search_results_max_nodes: int = 80


class AppConfig(BaseSettings):
    model_config = SettingsConfigDict(
        env_prefix="MUSIC_FREEGAL_",
        env_nested_delimiter="__",
        extra="ignore",
    )

    thresholds: ThresholdConfig = Field(default_factory=ThresholdConfig)
    playwright: PlaywrightConfig = Field(default_factory=PlaywrightConfig)

    @classmethod
    def load(cls, path: Path | None = None) -> AppConfig:
        import tomllib

        p = path or DEFAULT_CONFIG_PATH
        if not p.exists():
            LOG.warning("Config file missing at %s, using defaults", p)
            return cls()
        raw: dict[str, Any] = tomllib.loads(p.read_text(encoding="utf-8"))
        return cls(
            thresholds=ThresholdConfig.model_validate(raw.get("thresholds", {})),
            playwright=PlaywrightConfig.model_validate(raw.get("playwright", {})),
        )

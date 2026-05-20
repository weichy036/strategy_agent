from __future__ import annotations

from dataclasses import dataclass
import os
from pathlib import Path

from dotenv import load_dotenv


PACKAGE_ROOT = Path(__file__).resolve().parent
SRC_ROOT = PACKAGE_ROOT.parent
PROJECT_ROOT = SRC_ROOT.parent
DATA_ROOT = PROJECT_ROOT / "data"
DOCS_ROOT = PROJECT_ROOT / "docs"

load_dotenv(PROJECT_ROOT / ".env", override=True)


@dataclass(frozen=True)
class Settings:
    project_name: str = "strategy-agent"
    default_market: str = "CN"
    default_bar_frequency: str = "1d"
    default_start_date: str = "2018-01-01"
    adk_model: str = os.getenv("ADK_MODEL", "deepseek/deepseek-chat")
    data_root: Path = DATA_ROOT
    docs_root: Path = DOCS_ROOT
    raw_root: Path = DATA_ROOT / "raw"
    derived_root: Path = DATA_ROOT / "derived"
    artifact_root: Path = DATA_ROOT / "artifacts"

    @property
    def fund_daily_dir(self) -> Path:
        return self.raw_root / "fund_daily"

    @property
    def index_daily_dir(self) -> Path:
        return self.raw_root / "index_daily"

    @property
    def daily_basic_dir(self) -> Path:
        return self.raw_root / "daily_basic"

    @property
    def daily_qfq_dir(self) -> Path:
        return self.derived_root / "daily_qfq"


settings = Settings()

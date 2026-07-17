from __future__ import annotations

import os
from dataclasses import dataclass


@dataclass(frozen=True)
class Settings:
    database_url: str = "sqlite:///./.soloops/soloops.db"
    store_backend: str = "sqlalchemy"
    execution_enabled: bool = False


def get_settings() -> Settings:
    return Settings(
        database_url=os.getenv("SOLOOPS_DATABASE_URL", "sqlite:///./.soloops/soloops.db"),
        store_backend=os.getenv("SOLOOPS_STORE_BACKEND", "sqlalchemy"),
        execution_enabled=os.getenv("SOLOOPS_EXECUTION_ENABLED", "false").lower() == "true",
    )

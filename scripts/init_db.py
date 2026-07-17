from __future__ import annotations

from app.db import create_session_factory
from app.settings import get_settings


def main() -> None:
    settings = get_settings()
    create_session_factory(settings.database_url)
    print(f"Initialized SoloOps database: {settings.database_url}")


if __name__ == "__main__":
    main()

import os

import uvicorn


def main() -> None:
    host = os.getenv("SOLOOPS_HOST", "127.0.0.1")
    port = int(os.getenv("SOLOOPS_PORT", "8000"))
    uvicorn.run("app.api:app", host=host, port=port)


if __name__ == "__main__":
    main()

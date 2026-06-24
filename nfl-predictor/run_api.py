"""Run the NFL Prediction API server."""

import uvicorn

from src.config import settings


def main():
    uvicorn.run(
        "src.api.app:app",
        host="0.0.0.0",
        port=8000,
        reload=settings.is_dev,
        log_level="info",
    )


if __name__ == "__main__":
    main()

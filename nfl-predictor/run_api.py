"""Run the NFL Prediction API server."""

import os
import uvicorn


def main():
    is_dev = os.environ.get("ENV", "production") != "production"
    uvicorn.run(
        "src.api.app:app",
        host="0.0.0.0",
        port=8000,
        reload=is_dev,
        log_level="info",
    )


if __name__ == "__main__":
    main()

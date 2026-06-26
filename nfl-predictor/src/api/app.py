"""FastAPI application for NFL Prediction System."""

import logging
import time
import uuid

from fastapi import FastAPI, Request
from fastapi.middleware.cors import CORSMiddleware
from slowapi import Limiter, _rate_limit_exceeded_handler
from slowapi.util import get_remote_address
from slowapi.errors import RateLimitExceeded

from ..config import settings
from ..observability import setup_logging, metrics
from .routers import teams, games, predictions, fantasy, misc, matchup

setup_logging()
logger = logging.getLogger(__name__)

# Global rate limiter — keyed by client IP
limiter = Limiter(key_func=get_remote_address, default_limits=[])

app = FastAPI(
    title="NFL Prediction API",
    description="NFL game prediction system with historical data analysis",
    version="1.0.0",
)

app.state.limiter = limiter
app.add_exception_handler(RateLimitExceeded, _rate_limit_exceeded_handler)

# CORS — origins configurable via CORS_ORIGINS env (see src/config.py)
app.add_middleware(
    CORSMiddleware,
    allow_origins=list(settings.cors_origins),
    allow_credentials=False,
    allow_methods=["GET", "POST", "DELETE"],
    allow_headers=["Content-Type"],
)


@app.middleware("http")
async def observe_requests(request: Request, call_next):
    """Assign a request id, time the request, record metrics, log structured line."""
    request_id = request.headers.get("X-Request-ID") or uuid.uuid4().hex[:12]
    start = time.perf_counter()
    status = 500
    try:
        response = await call_next(request)
        status = response.status_code
        response.headers["X-Request-ID"] = request_id
        return response
    finally:
        duration_ms = (time.perf_counter() - start) * 1000.0
        metrics.record_request(status, duration_ms)
        logger.info(
            "request",
            extra={"extra_fields": {
                "request_id": request_id,
                "method": request.method,
                "path": request.url.path,
                "status": status,
                "duration_ms": round(duration_ms, 2),
            }},
        )


@app.exception_handler(Exception)
async def global_exception_handler(request, exc):
    from fastapi.responses import JSONResponse
    logger.error("Unhandled exception: %s", exc, exc_info=True)
    return JSONResponse(status_code=500, content={"detail": "Internal server error"})


app.include_router(teams.router)
app.include_router(games.router)
app.include_router(predictions.router)
app.include_router(fantasy.router)
app.include_router(matchup.router)
app.include_router(misc.router)

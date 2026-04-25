"""FastAPI application for NFL Prediction System."""

import logging

from fastapi import FastAPI, Request
from fastapi.middleware.cors import CORSMiddleware
from slowapi import Limiter, _rate_limit_exceeded_handler
from slowapi.util import get_remote_address
from slowapi.errors import RateLimitExceeded

from .routers import teams, games, predictions, fantasy, misc

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

# CORS — allow frontend dev server
app.add_middleware(
    CORSMiddleware,
    allow_origins=["http://localhost:5173", "http://localhost:3000", "http://127.0.0.1:5173"],
    allow_credentials=False,
    allow_methods=["GET", "POST", "DELETE"],
    allow_headers=["Content-Type"],
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
app.include_router(misc.router)

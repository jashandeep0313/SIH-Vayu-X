"""Vayu-X API gateway.

Single entry point for the dashboard and external consumers. Orchestrates the model
service and the alert service, persists results, and pushes live updates over WebSocket.
"""

from contextlib import asynccontextmanager

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from app.api.v1.router import api_router
from app.core.config import settings
from app.services.websocket import connection_manager


@asynccontextmanager
async def lifespan(app: FastAPI):
    # TODO(backend): open DB pool, Redis connection, warm downstream health checks
    yield
    # TODO(backend): close connections


app = FastAPI(
    title=settings.PROJECT_NAME,
    version=settings.VERSION,
    description=(
        "AI/ML system for identification, classification and prediction of tropical "
        "cyclone patterns from multi-source satellite data. "
        "SIH PS 26070 — Team Vayu-X (152)."
    ),
    docs_url="/docs",
    redoc_url="/redoc",
    lifespan=lifespan,
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.cors_origins_list,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

app.include_router(api_router, prefix=settings.API_V1_PREFIX)


@app.get("/", tags=["meta"])
async def root() -> dict:
    return {
        "service": "vayux-backend",
        "version": settings.VERSION,
        "problem_statement": "26070",
        "team": "Vayu-X (152)",
        "docs": "/docs",
    }


app.add_api_websocket_route("/ws", connection_manager.endpoint)

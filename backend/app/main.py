"""RESQ backend entrypoint (Section 26)."""

from __future__ import annotations

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from app.api import analysis, network, scenarios
from app.state_store import store

app = FastAPI(title="RESQ - Cascading Infrastructure Failure & Resilience API", version="0.1.0")

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],  # MVP only; tighten before anything beyond a hackathon demo
    allow_methods=["*"],
    allow_headers=["*"],
)

app.include_router(network.router)
app.include_router(scenarios.router)
app.include_router(analysis.router)


@app.on_event("startup")
def startup():
    store.load_demo()


@app.get("/")
def root():
    return {"status": "ok", "service": "RESQ backend"}

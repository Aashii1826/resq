"""
RESQ backend entrypoint.

Run locally:
    PYTHONPATH=. uvicorn app.main:app --reload --port 8000

Then visit http://127.0.0.1:8000/docs for interactive API docs.
"""

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from app.api import analysis, network, scenarios
from app.state import init_state

app = FastAPI(title="RESQ API", version="0.1.0")

# open CORS for the hackathon - frontend runs on a different port (Vite)
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_methods=["*"],
    allow_headers=["*"],
)

app.include_router(network.router, tags=["network"])
app.include_router(analysis.router, tags=["analysis"])
app.include_router(scenarios.router, tags=["scenarios"])


@app.on_event("startup")
def startup():
    # loads the deterministic demo network + baseline once, shared by all requests
    init_state(mode="demo")


@app.get("/")
def root():
    return {"status": "ok", "service": "RESQ API", "docs": "/docs"}

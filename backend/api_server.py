"""
AlgoDesk API Server Entry Point.
Runs the FastAPI server with the router defined in api/server.py.
"""

import sys
import os
import uvicorn
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

# Ensure backend directory is in the import path
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from api.server import router

app = FastAPI(
    title="AlgoDesk API",
    description="Multi-Agent Quant Debate backend service",
    version="1.0.0"
)

# Enable CORS for frontend development
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

@app.get("/")
async def root():
    return {
        "message": "AlgoDesk API is running.",
        "docs": "/docs",
        "health": "/api/health"
    }

app.include_router(router)

if __name__ == "__main__":
    uvicorn.run("api_server:app", host="0.0.0.0", port=8000, reload=False)

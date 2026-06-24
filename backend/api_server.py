"""
AlgoDesk API Server Entry Point.
Runs the FastAPI server with the router defined in api/server.py.
"""

import sys
import os

# Ensure backend directory is in the import path and force local 'tools' precedence
backend_dir = os.path.dirname(os.path.abspath(__file__))
if backend_dir not in sys.path:
    sys.path.insert(0, backend_dir)

backend_dir_normalized = backend_dir.replace('\\', '/')

if 'tools' in sys.modules:
    tools_mod = sys.modules['tools']
    is_our_tools = False
    if hasattr(tools_mod, '__file__') and tools_mod.__file__:
        file_path = os.path.abspath(tools_mod.__file__).replace('\\', '/')
        if file_path.startswith(backend_dir_normalized) and 'tools' in file_path:
            is_our_tools = True
    if not is_our_tools:
        del sys.modules['tools']

if 'analytics' in sys.modules:
    analytics_mod = sys.modules['analytics']
    is_our_analytics = False
    if hasattr(analytics_mod, '__file__') and analytics_mod.__file__:
        file_path = os.path.abspath(analytics_mod.__file__).replace('\\', '/')
        if file_path.startswith(backend_dir_normalized) and 'analytics' in file_path:
            is_our_analytics = True
    if not is_our_analytics:
        for mod_name in list(sys.modules.keys()):
            if mod_name == 'analytics' or mod_name.startswith('analytics.'):
                del sys.modules[mod_name]

# Force-import local packages immediately to cache them in sys.modules
import tools
import analytics

import uvicorn
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

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
    allow_credentials=False,
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
    import os
    port = int(os.environ.get("PORT", 8000))
    uvicorn.run("api_server:app", host="0.0.0.0", port=port, reload=False)

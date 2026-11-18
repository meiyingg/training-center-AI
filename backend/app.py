"""Compatibility entrypoint for the FastAPI application.

Run locally with ``python backend/app.py`` or in production with
``uvicorn backend.main:app``.
"""
import os

import uvicorn

try:
    from .main import app
except ImportError:
    from main import app


if __name__ == "__main__":
    uvicorn.run(app, host="0.0.0.0", port=int(os.getenv("PORT", "8000")))

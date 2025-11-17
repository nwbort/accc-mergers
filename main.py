"""
Wrapper module for Railway deployment.
This allows Railway to find the app at the root level while keeping the actual
implementation in merger-tracker/backend/
"""
import sys
from pathlib import Path

# Add the backend directory to Python path
backend_path = Path(__file__).parent / "merger-tracker" / "backend"
sys.path.insert(0, str(backend_path))

# Import the FastAPI app from the backend
from main import app

__all__ = ["app"]

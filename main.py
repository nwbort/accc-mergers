"""
Wrapper module for Railway deployment.
This allows Railway to find the app at the root level while keeping the actual
implementation in merger-tracker/backend/
"""
import sys
import os
from pathlib import Path
import importlib.util

# Add the backend directory to Python path so that modules can import each other
backend_path = Path(__file__).parent / "merger-tracker" / "backend"
sys.path.insert(0, str(backend_path))

# Change working directory to backend so relative file paths work
os.chdir(str(backend_path))

# Import the main module from backend using importlib to avoid circular imports
main_path = backend_path / "main.py"
spec = importlib.util.spec_from_file_location("backend_main", main_path)
backend_main = importlib.util.module_from_spec(spec)
spec.loader.exec_module(backend_main)

# Export the app
app = backend_main.app

__all__ = ["app"]

#!/bin/bash
set -e

# Print debug information
echo "Current directory: $(pwd)"
echo "Contents of current directory:"
ls -la
echo ""
echo "Looking for merger-tracker/backend:"
ls -la merger-tracker/backend/ || echo "Backend directory not found!"
echo ""

# Change to backend directory
cd merger-tracker/backend

echo "Changed to: $(pwd)"
echo "Contents:"
ls -la
echo ""
echo "Starting uvicorn..."

# Start the application
exec uvicorn main:app --host 0.0.0.0 --port "${PORT:-8000}"

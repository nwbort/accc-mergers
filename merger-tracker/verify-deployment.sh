#!/bin/bash

# Deployment Verification Script
# This script checks if both frontend and backend are ready for deployment

set -e

echo "🔍 Verifying deployment readiness for ACCC Merger Tracker..."
echo ""

# Colors for output
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
NC='\033[0m' # No Color

ERRORS=0

# Function to print status
print_status() {
    if [ $1 -eq 0 ]; then
        echo -e "${GREEN}✓${NC} $2"
    else
        echo -e "${RED}✗${NC} $2"
        ERRORS=$((ERRORS + 1))
    fi
}

# Check Backend
echo "📦 Checking Backend..."
echo "-------------------"

cd backend

# Check if requirements.txt exists
if [ -f "requirements.txt" ]; then
    print_status 0 "requirements.txt exists"
else
    print_status 1 "requirements.txt missing"
fi

# Check if main.py exists
if [ -f "main.py" ]; then
    print_status 0 "main.py exists"
else
    print_status 1 "main.py missing"
fi

# Check if railway.json exists
if [ -f "railway.json" ]; then
    print_status 0 "railway.json exists"
else
    print_status 1 "railway.json missing"
fi

# Check if Procfile exists
if [ -f "Procfile" ]; then
    print_status 0 "Procfile exists"
else
    print_status 1 "Procfile missing"
fi

# Check Python version
if command -v python3 &> /dev/null; then
    PYTHON_VERSION=$(python3 --version | cut -d' ' -f2)
    print_status 0 "Python 3 installed (version $PYTHON_VERSION)"
else
    print_status 1 "Python 3 not installed"
fi

# Try to install dependencies (optional, commented out for CI)
# echo ""
# echo "Installing Python dependencies..."
# python3 -m pip install -r requirements.txt --quiet
# print_status $? "Backend dependencies installed"

# Check if main.py imports work
echo ""
echo "Checking Python imports..."
if python3 -c "from fastapi import FastAPI; from database import get_db" 2>/dev/null; then
    print_status 0 "Backend imports valid"
else
    print_status 1 "Backend imports failed (dependencies may not be installed)"
fi

echo ""

# Check Frontend
echo "🎨 Checking Frontend..."
echo "-------------------"

cd ../frontend

# Check if package.json exists
if [ -f "package.json" ]; then
    print_status 0 "package.json exists"
else
    print_status 1 "package.json missing"
fi

# Check if index.html exists
if [ -f "index.html" ]; then
    print_status 0 "index.html exists"
else
    print_status 1 "index.html missing"
fi

# Check if vite.config.js exists
if [ -f "vite.config.js" ]; then
    print_status 0 "vite.config.js exists"
else
    print_status 1 "vite.config.js missing"
fi

# Check if .node-version exists
if [ -f ".node-version" ]; then
    print_status 0 ".node-version exists"
else
    print_status 1 ".node-version missing"
fi

# Check if _redirects exists in public
if [ -f "public/_redirects" ]; then
    print_status 0 "public/_redirects exists (for Cloudflare Pages SPA routing)"
else
    print_status 1 "public/_redirects missing"
fi

# Check Node version
if command -v node &> /dev/null; then
    NODE_VERSION=$(node --version)
    print_status 0 "Node.js installed (version $NODE_VERSION)"
else
    print_status 1 "Node.js not installed"
fi

# Check npm
if command -v npm &> /dev/null; then
    NPM_VERSION=$(npm --version)
    print_status 0 "npm installed (version $NPM_VERSION)"
else
    print_status 1 "npm not installed"
fi

# Try to install dependencies (optional)
# echo ""
# echo "Installing npm dependencies..."
# npm install --silent
# print_status $? "Frontend dependencies installed"

# Try to build (optional, takes time)
# echo ""
# echo "Testing frontend build..."
# npm run build
# print_status $? "Frontend build successful"

echo ""
echo "═══════════════════════════════════════"

if [ $ERRORS -eq 0 ]; then
    echo -e "${GREEN}✓ All checks passed!${NC}"
    echo "Your application is ready for deployment! 🚀"
    echo ""
    echo "Next steps:"
    echo "1. Commit your changes: git add . && git commit -m 'Add deployment configuration'"
    echo "2. Push to GitHub: git push"
    echo "3. Follow the deployment guide: CLOUDFLARE_RAILWAY_DEPLOYMENT.md"
    exit 0
else
    echo -e "${RED}✗ Found $ERRORS error(s)${NC}"
    echo "Please fix the errors above before deploying."
    exit 1
fi

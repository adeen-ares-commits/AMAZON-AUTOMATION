#!/bin/bash

echo "========================================"
echo "Amazon Automation FastAPI Backend"
echo "========================================"

# Check if Python is installed
if ! command -v python3 &> /dev/null; then
    echo "ERROR: Python 3 is not installed or not in PATH"
    echo "Please install Python from https://python.org/"
    exit 1
fi

echo "Python found:"
python3 --version

# Check if pip is available
if ! command -v pip3 &> /dev/null; then
    echo "ERROR: pip3 is not available"
    echo "Please ensure pip is installed with Python"
    exit 1
fi

echo "pip found:"
pip3 --version

# Navigate to backend directory
cd "$(dirname "$0")"

echo ""
echo "Installing Python dependencies..."
pip3 install -r requirements.txt

if [ $? -ne 0 ]; then
    echo "ERROR: Failed to install dependencies"
    exit 1
fi

echo ""
echo "Installing Playwright browsers..."
playwright install chromium

if [ $? -ne 0 ]; then
    echo "WARNING: Failed to install Playwright browsers"
    echo "You may need to install them manually: playwright install chromium"
fi

echo ""
echo "Starting FastAPI backend server..."
echo "Backend will be available at: http://localhost:4000"
echo "API documentation at: http://localhost:4000/docs"
echo ""
echo "Press Ctrl+C to stop the server"
echo "========================================"

python3 main.py

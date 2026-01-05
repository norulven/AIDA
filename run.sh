#!/bin/bash
# Run Aida AI Assistant

cd "$(dirname "$0")"

# Check if virtual environment exists
if [ ! -d ".venv" ]; then
    echo "Creating virtual environment..."
    python -m venv .venv
fi

# Activate virtual environment
source .venv/bin/activate

# Install dependencies if needed
if [ ! -f ".venv/.installed" ]; then
    echo "Installing dependencies..."
    pip install -e ".[dev]"

    # Install Playwright browsers
    python -m playwright install chromium

    touch .venv/.installed
fi

# Run Aida
python -m src.main "$@"

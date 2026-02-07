#!/bin/bash
# Run the Kleine Anfragen Search UI

SCRIPT_DIR="$(cd "$(dirname "$0")" && pwd)"
cd "$SCRIPT_DIR"

# Create and activate virtual environment
VENV_DIR="$SCRIPT_DIR/venv"
if [[ ! -d "$VENV_DIR" ]]; then
    echo "Creating virtual environment in $VENV_DIR ..."
    python3 -m venv "$VENV_DIR"
fi
source "$VENV_DIR/bin/activate"

cd backend

# Check if requirements are installed
python -c "import fastapi" 2>/dev/null || {
    echo "Installing dependencies..."
    pip install -r requirements.txt
}

echo "Starting Kleine Anfragen Search API..."
echo "Open http://localhost:8000 in your browser"
echo ""

python main.py

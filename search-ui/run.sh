#!/bin/bash
# Run the Kleine Anfragen Search UI

cd "$(dirname "$0")/backend"

# Check if requirements are installed
python -c "import fastapi" 2>/dev/null || {
    echo "Installing dependencies..."
    pip install -r requirements.txt
}

echo "Starting Kleine Anfragen Search API..."
echo "Open http://localhost:8000 in your browser"
echo ""

python main.py

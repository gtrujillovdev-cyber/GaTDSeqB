#!/bin/bash
ROOT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
cd "$ROOT_DIR"

if [ -d ".venv" ]; then
    source .venv/bin/activate
fi

# Clean previous hanging processes
pkill -f "python3 server.py" > /dev/null 2>&1

if ! pgrep -f "python3 bot.py" > /dev/null; then
    nohup python3 bot.py > /dev/null 2>&1 &
fi

echo "====================================================="
echo "   🚀 GATDSEQ TELEMETRY & KIOSK SERVER STARTUP       "
echo "====================================================="
echo ""
echo "👉 Bloomberg Kiosk URL: http://localhost:5001/lite"
echo ""
python3 server.py

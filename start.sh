#!/bin/bash
cd ~/Documents/GtrujilloMacDoc/GitHub/GitGa/Developer/Projects/GaTDSEQ
source .venv/bin/activate

# Matar procesos anteriores por si acaso
pkill -f "streamlit run dashboard.py" > /dev/null 2>&1
pkill -f "python3 server.py" > /dev/null 2>&1

if ! pgrep -f "python3 bot.py" > /dev/null; then
    nohup python3 bot.py > /dev/null 2>&1 &
fi

echo "====================================================="
echo "   🚀 SERVIDOR DEL DASHBOARD PROFESIONAL INICIADO   "
echo "====================================================="
echo ""
echo "👉 Abre tu navegador web y entra en: http://localhost:5001"
echo ""
python3 server.py

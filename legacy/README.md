# 🗄️ Legacy Code Archive

This directory contains deprecated and prototype modules from the initial developmental phases of GaTDSEQ:

- `backtest.py`: Day 1 prototype single-asset backtesting script. Superseded by the high-performance event-driven engine in `backtesting/` and `run_backtest.py`.
- `dashboard.py`: Day 1 Streamlit prototype web interface. Superseded by the zero-latency Flask-SocketIO WebSockets server in `server.py` and `templates/lite.html`.
- `index.html`: Early prototype Tailwind CSS dashboard template. Superseded by the institutional Bloomberg Terminal 21:9 UI in `templates/lite.html`.

*These files are preserved strictly for historical development reference and are not invoked by active production services.*

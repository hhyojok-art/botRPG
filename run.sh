#!/bin/bash
# Run FastAPI dashboard in background
uvicorn dashboard.app:app --host 0.0.0.0 --port $REPLIT_PORT &
# Run Discord bot
python main.py

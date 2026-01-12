#!/usr/bin/env bash
set -e

echo "Starting Replit launch script..."

# Install requirements only once to avoid long startup on subsequent deploys
DEPS_MARKER=".replit_deps_installed"
if [ ! -f "$DEPS_MARKER" ]; then
  echo "Installing dependencies (this runs only once)..."
  python -m pip install --upgrade pip
  pip install -r requirements.txt
  touch "$DEPS_MARKER"
else
  echo "Dependencies already installed; skipping install."
fi

# Optional: build frontend if requested
if [ "${BUILD_FRONTEND:-0}" = "1" ]; then
  if command -v npm >/dev/null 2>&1; then
    echo "BUILD_FRONTEND=1 detected — building frontend..."
    pushd frontend >/dev/null 2>&1 || true
    # prefer ci for reproducible installs if package-lock exists
    if [ -f package-lock.json ]; then
      npm ci --silent || npm install --silent
    else
      npm install --silent || true
    fi
    npm run build --silent || echo "frontend build failed; continuing"
    popd >/dev/null 2>&1 || true
  else
    echo "npm not found — skipping frontend build"
  fi
fi

# Use Replit-provided PORT if available
PORT=${PORT:-8000}

# If TOKEN is not set, run only the dashboard to avoid Discord login errors
if [ -z "$TOKEN" ]; then
  echo "TOKEN is not set. Starting dashboard only. Set TOKEN in Replit Secrets to run the bot."
  # ensure logs dir exists and write startup line
  mkdir -p logs || true
  echo "$(date -u +%Y-%m-%dT%H:%M:%SZ) | starting dashboard only on port $PORT" >> logs/replit_startup.log || true
  exec uvicorn dashboard.app:app --host 0.0.0.0 --port $PORT --loop auto
else
  echo "TOKEN present. Starting bot (background) and dashboard (foreground)."
  mkdir -p logs || true
  echo "$(date -u +%Y-%m-%dT%H:%M:%SZ) | starting bot in background and dashboard on port $PORT" >> logs/replit_startup.log || true
  python main.py &
  exec uvicorn dashboard.app:app --host 0.0.0.0 --port $PORT --loop auto
fi

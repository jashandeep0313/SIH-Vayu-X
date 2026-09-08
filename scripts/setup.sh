#!/usr/bin/env bash
# Vayu-X — first-time setup (Linux / macOS)
set -euo pipefail

cd "$(dirname "$0")/.."

echo "=== Vayu-X setup — Team 152 ==="

# ---------- .env ----------
if [ ! -f .env ]; then
  cp .env.example .env
  echo "  Created .env from template — fill in your credentials before ingesting data"
else
  echo "  .env already exists, leaving it alone"
fi

# ---------- Python services ----------
for service in backend ai-model alert-system data-pipeline; do
  echo ""
  echo "--- $service ---"
  (
    cd "$service"
    python3 -m venv .venv
    # shellcheck disable=SC1091
    source .venv/bin/activate
    pip install --quiet --upgrade pip
    pip install --quiet -r requirements.txt
    echo "  dependencies installed"
  )
done

# ---------- Frontend ----------
echo ""
echo "--- frontend ---"
(cd frontend && npm install --silent && echo "  dependencies installed")

cat <<'EOF'

=== Setup complete ===

Next steps:
  1. Fill credentials in .env  (MOSDAC, Earthdata, CDS — see docs/data-sources.md)
  2. Start the stack:          docker compose up
  3. Or run services individually — see each service's README

  Dashboard      http://localhost:5173
  Backend docs   http://localhost:8000/docs
  Model docs     http://localhost:8001/docs
  Alert docs     http://localhost:8002/docs

Note: ALERT_DRY_RUN defaults to true — alerts are logged, not sent.
EOF

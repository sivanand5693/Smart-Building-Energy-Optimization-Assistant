#!/usr/bin/env bash
# init.sh -- Verify the project builds cleanly before starting work.
# Run this after cloning or when resuming work.
set -euo pipefail

echo "=== Project Init ==="
echo ""

# 1. Python virtual environment
echo "[1/6] Checking Python venv..."
if [ ! -d ".venv" ]; then
  echo "  .venv not found. Creating with python3.12..."
  python3.12 -m venv .venv
fi
# shellcheck disable=SC1091
source .venv/bin/activate
echo "  venv active: $(python --version)"
echo ""

# 2. Python dependencies
echo "[2/6] Installing Python dependencies..."
pip install -q -r requirements.txt
echo ""

# 3. Node dependencies
echo "[3/6] Installing Node dependencies..."
( cd frontend && npm install --silent )
echo ""

# 4. Frontend type check + build
echo "[4/6] Running frontend type check + build..."
( cd frontend && npm run build )
echo ""

# 5. Database availability check
echo "[5/6] Verifying PostgreSQL databases..."
if ! command -v psql >/dev/null 2>&1; then
  echo "  WARNING: psql not on PATH. Install postgresql@16 and add it to PATH."
else
  for db in smart_building_dev smart_building_test; do
    if psql -lqt | cut -d \| -f 1 | grep -qw "$db"; then
      echo "  ✓ $db exists"
    else
      echo "  ✗ $db missing — run: createdb $db"
    fi
  done
fi
echo ""

# 6. Apply migrations to test DB so acceptance tests can run
echo "[6/6] Applying migrations to test DB..."
( cd backend && TESTING=1 alembic upgrade head ) || echo "  WARNING: alembic upgrade failed — DB may be missing or unreachable."
echo ""

echo "=== Init complete. ==="
echo "Backend dev:    cd backend && uvicorn app.main:app --reload"
echo "Frontend dev:   cd frontend && npm run dev"
echo "Acceptance:     PYTHONPATH=\"./backend:.\" behave tests/acceptance/features/"

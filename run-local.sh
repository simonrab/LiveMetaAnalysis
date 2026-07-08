#!/usr/bin/env bash
# Run the LiveMeta backend locally against Supabase, fetching CT.gov live.
# Loads secrets from .env (gitignored), then starts the API on :8000.
# Front end: in another terminal run `npm --prefix web run dev`, open :5173.
set -euo pipefail
cd "$(dirname "$0")"

if [[ ! -f .env ]]; then
  echo "Missing .env (expected DATABASE_URL). See .env.example or the README." >&2
  exit 1
fi

set -a
# shellcheck disable=SC1091
source .env
set +a

exec .venv/bin/python -m uvicorn livemeta.api.app:app --port 8000 --reload

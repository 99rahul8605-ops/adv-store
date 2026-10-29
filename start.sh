#!/usr/bin/env bash
set -euo pipefail
cd "$(dirname "$0")"
if [ ! -f .env ]; then
  echo 'Warning: .env missing; configure required environment variables before starting.' >&2
fi
if [ ! -x venv/bin/python ]; then
  python3 -m venv venv
fi
venv/bin/python -m pip install -r requirements.txt
exec venv/bin/python -u main.py

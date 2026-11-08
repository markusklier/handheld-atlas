#!/bin/sh
cd "$(dirname "$0")" || exit 1
if ! command -v python3 >/dev/null 2>&1; then
  echo "Python 3.10+ is required. Install Python, then run this file again."
  exit 1
fi
python3 scripts/serve.py

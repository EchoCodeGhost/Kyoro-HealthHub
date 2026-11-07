#!/bin/sh
# Copy the unchanged pipeline code and config/ into the app sources (not
# committed). config/ must sit next to kyoro_scripts/ because scripts read
# scripts/../config (for example compute_symptoms.py -> symptom_map.json).
set -eu
cd "$(dirname "$0")"
rm -rf src/kyoro_scripts src/config
mkdir -p src/kyoro_scripts
cp -R ../../scripts/. src/kyoro_scripts/
find src/kyoro_scripts -name __pycache__ -type d -prune -exec rm -rf {} +
touch src/kyoro_scripts/__init__.py
cp -R ../../config src/config
echo "Copied $(find src/kyoro_scripts -name '*.py' | wc -l | tr -d ' ') Python files."

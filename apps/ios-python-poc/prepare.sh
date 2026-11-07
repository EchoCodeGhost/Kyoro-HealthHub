#!/bin/sh
# Copy the unchanged pipeline code into the app sources (not committed).
set -eu
cd "$(dirname "$0")"
rm -rf src/kyoro_scripts
mkdir -p src/kyoro_scripts
cp -R ../../scripts/. src/kyoro_scripts/
find src/kyoro_scripts -name __pycache__ -type d -prune -exec rm -rf {} +
touch src/kyoro_scripts/__init__.py
echo "Copied $(find src/kyoro_scripts -name '*.py' | wc -l | tr -d ' ') Python files."

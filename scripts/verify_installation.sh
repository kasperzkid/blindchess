#!/usr/bin/env bash
# BlindChess Installation Verification Script
set -euo pipefail

echo "============================================================"
echo "          BlindChess Installation Verification             "
echo "============================================================"

# Test CLI executable
if command -v blindchess &>/dev/null; then
    echo "✓ blindchess executable found in PATH: $(command -v blindchess)"
    blindchess --help >/dev/null
    echo "✓ CLI arguments verified."
else
    echo "! blindchess executable not found in PATH."
    echo "  (Try running: export PATH=\"\$HOME/.local/bin:\$PATH\")"
fi

# Detect launcher or virtual environment python
PY_CMD=""
if [ -f "$HOME/.local/share/blindchess/venv/bin/python3" ]; then
    PY_CMD="$HOME/.local/share/blindchess/venv/bin/python3"
elif [ -f "./.venv/bin/python3" ]; then
    PY_CMD="./.venv/bin/python3"
else
    PY_CMD="python3"
fi

# Test Python module
"$PY_CMD" -c "import blindchess; print(f'✓ blindchess package v{blindchess.__version__} successfully imported.')"

# Test python-chess dependency
"$PY_CMD" -c "import chess; print(f'✓ Authoritative python-chess v{chess.__version__} ready.')"

# Test Stockfish engine
if command -v stockfish &>/dev/null; then
    echo "✓ Stockfish engine located: $(command -v stockfish)"
    stockfish uci | head -n 2
else
    echo "• Stockfish is not in PATH. Engine-free features remain fully active."
fi

echo "============================================================"
echo "Verification complete!"
echo "============================================================"

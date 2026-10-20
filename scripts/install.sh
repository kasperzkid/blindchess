#!/usr/bin/env bash
# BlindChess Installation Script for Linux
set -euo pipefail

echo "============================================================"
echo "          BlindChess Linux Installation Script             "
echo "============================================================"

# 1. Check Python version
if ! command -v python3 &>/dev/null; then
    echo "ERROR: python3 is not installed or not in PATH."
    exit 1
fi

PY_VERSION=$(python3 -c 'import sys; print(f"{sys.version_info.major}.{sys.version_info.minor}")')
echo "Detected Python version: $PY_VERSION"

# 2. Check Stockfish executable
echo "Checking for Stockfish chess engine..."
if command -v stockfish &>/dev/null; then
    SF_PATH=$(command -v stockfish)
    echo "Stockfish located at: $SF_PATH"
elif [ -f "$HOME/.local/bin/stockfish" ]; then
    echo "Stockfish located at: $HOME/.local/bin/stockfish"
else
    echo "NOTICE: Stockfish was not found in standard system paths."
    echo "BlindChess will run in engine-free mode (legal moves, blindfold exercises, PGN tools)."
    echo "To install Stockfish for engine sparring & deep analysis:"
    echo "  • Ubuntu/Debian:  sudo apt install stockfish"
    echo "  • Arch Linux:     sudo pacman -S stockfish"
    echo "  • Fedora:         sudo dnf install stockfish"
fi

# 3. Virtual Environment setup
VENV_DIR="${HOME}/.local/share/blindchess/venv"
echo "Creating/updating isolated virtualenv in $VENV_DIR..."
mkdir -p "$(dirname "$VENV_DIR")"
python3 -m venv "$VENV_DIR"

echo "Installing BlindChess into virtualenv..."
"$VENV_DIR/bin/pip" install --upgrade pip
"$VENV_DIR/bin/pip" install .

# 4. Create launcher symlink in ~/.local/bin
mkdir -p "$HOME/.local/bin"
LAUNCHER="$HOME/.local/bin/blindchess"
cat << 'EOF' > "$LAUNCHER"
#!/usr/bin/env bash
exec "$HOME/.local/share/blindchess/venv/bin/blindchess" "$@"
EOF
chmod +x "$LAUNCHER"

echo "============================================================"
echo "Installation complete!"
echo "Launcher created at: $LAUNCHER"
echo ""
echo "To ensure ~/.local/bin is in your PATH, check:"
echo "  export PATH=\"\$HOME/.local/bin:\$PATH\""
echo ""
echo "Launch BlindChess by typing:"
echo "  blindchess"
echo "============================================================"

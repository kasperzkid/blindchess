#!/usr/bin/env bash
# BlindChess Uninstallation Script
set -euo pipefail

echo "============================================================"
echo "          BlindChess Uninstallation Script                 "
echo "============================================================"

LAUNCHER="$HOME/.local/bin/blindchess"
VENV_DIR="$HOME/.local/share/blindchess/venv"
DATA_DIR="$HOME/.local/share/blindchess"
CONFIG_DIR="$HOME/.config/blindchess"

if [ -f "$LAUNCHER" ]; then
    echo "Removing launcher: $LAUNCHER"
    rm -f "$LAUNCHER"
fi

if [ -d "$VENV_DIR" ]; then
    echo "Removing isolated virtual environment: $VENV_DIR"
    rm -rf "$VENV_DIR"
fi

echo ""
echo "Do you wish to delete your training history database and saved PGNs?"
echo "Directory: $DATA_DIR"
read -rp "Delete training data? [y/N]: " REMOVE_DATA

if [[ "$REMOVE_DATA" =~ ^[Yy]$ ]]; then
    echo "Removing data directory..."
    rm -rf "$DATA_DIR"
    echo "Data removed."
else
    echo "Preserving training data in $DATA_DIR."
fi

echo ""
read -rp "Delete configuration settings ($CONFIG_DIR)? [y/N]: " REMOVE_CONF
if [[ "$REMOVE_CONF" =~ ^[Yy]$ ]]; then
    echo "Removing configuration..."
    rm -rf "$CONFIG_DIR"
    echo "Config removed."
else
    echo "Preserving configuration."
fi

echo "============================================================"
echo "BlindChess has been uninstalled."
echo "============================================================"

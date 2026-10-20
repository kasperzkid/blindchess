#!/usr/bin/env bash
# ==============================================================================
# BlindChess Uninstallation Script
# Removes launcher, virtual environment, and optional data files.
# ==============================================================================
set -euo pipefail

BIN_DIR="${HOME}/.local/bin"
DATA_DIR="${HOME}/.local/share/blindchess"
VENV_DIR="${DATA_DIR}/venv"
CONFIG_DIR="${HOME}/.config/blindchess"
LAUNCHER="${BIN_DIR}/blindchess"
GLOBAL_LAUNCHER="/usr/local/bin/blindchess"

# ANSI Colors
BOLD="\033[1m"
CYAN="\033[1;36m"
GREEN="\033[1;32m"
YELLOW="\033[1;33m"
RED="\033[1;31m"
MUTED="\033[0;90m"
RESET="\033[0m"

echo -e "${CYAN}======================================================================${RESET}"
echo -e "${BOLD}                    BlindChess Uninstaller                            ${RESET}"
echo -e "${CYAN}======================================================================${RESET}"

PURGE_DATA=""
for arg in "$@"; do
    case "$arg" in
        --purge)
            PURGE_DATA="true"
            ;;
        --keep-data)
            PURGE_DATA="false"
            ;;
        -h|--help)
            echo "Usage: ./uninstall.sh [OPTIONS]"
            echo ""
            echo "Options:"
            echo "  --purge        Completely remove all training history, database, and configs"
            echo "  --keep-data    Retain training progress database and configs (removes software only)"
            echo "  -h, --help     Show this help message"
            exit 0
            ;;
    esac
done

# 1. Remove Launchers
echo -e "${BOLD}[1/3] Removing executable launchers...${RESET}"
if [ -f "$LAUNCHER" ]; then
    rm -f "$LAUNCHER"
    echo -e "${GREEN}✓ Removed launcher:${RESET} $LAUNCHER"
fi

if [ -L "$GLOBAL_LAUNCHER" ] || [ -f "$GLOBAL_LAUNCHER" ]; then
    if [ -w "$GLOBAL_LAUNCHER" ]; then
        rm -f "$GLOBAL_LAUNCHER"
        echo -e "${GREEN}✓ Removed global launcher:${RESET} $GLOBAL_LAUNCHER"
    elif command -v sudo &>/dev/null; then
        sudo rm -f "$GLOBAL_LAUNCHER" 2>/dev/null || true
    fi
fi

# 2. Remove Virtual Environment
echo -e "${BOLD}[2/3] Removing isolated Python environment...${RESET}"
if [ -d "$VENV_DIR" ]; then
    rm -rf "$VENV_DIR"
    echo -e "${GREEN}✓ Removed virtual environment:${RESET} $VENV_DIR"
fi

# 3. Handle Training Data and Configuration
echo -e "${BOLD}[3/3] Checking training history & database...${RESET}"
if [ -z "$PURGE_DATA" ]; then
    echo ""
    echo -e "Your training progress, adaptive difficulty ratings, and stats are saved in:"
    echo -e "  ${MUTED}$DATA_DIR${RESET}"
    echo ""
    read -rp "Do you wish to DELETE your training history database? [y/N]: " USER_CHOICE
    if [[ "$USER_CHOICE" =~ ^[Yy]$ ]]; then
        PURGE_DATA="true"
    else
        PURGE_DATA="false"
    fi
fi

if [ "$PURGE_DATA" = "true" ]; then
    echo "Purging training data and configuration..."
    [ -d "$DATA_DIR" ] && rm -rf "$DATA_DIR"
    [ -d "$CONFIG_DIR" ] && rm -rf "$CONFIG_DIR"
    echo -e "${GREEN}✓ All training database records and configurations purged.${RESET}"
else
    echo -e "${GREEN}✓ Preserving user data in:${RESET} $DATA_DIR"
fi

echo ""
echo -e "${CYAN}======================================================================${RESET}"
echo -e "${GREEN}${BOLD}             BlindChess has been successfully uninstalled.            ${RESET}"
echo -e "${CYAN}======================================================================${RESET}"

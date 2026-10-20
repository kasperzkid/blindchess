# BlindChess Installation Guide

This guide covers installing and configuring BlindChess on Linux systems.

## Prerequisites

- Modern Linux distribution (Ubuntu, Debian, Fedora, Arch Linux, openSUSE, Alpine, etc.)
- Python 3.10+
- (Recommended) Stockfish chess engine binary

---

## Method 1: Automated User Installation (Recommended)

Run the included install script:
```bash
./scripts/install.sh
```
This script will:
1. Verify Python version compatibility.
2. Check for Stockfish in PATH and common Linux paths.
3. Create an isolated virtual environment at `~/.local/share/blindchess/venv`.
4. Install `blindchess` and its dependencies.
5. Create a standalone launcher script at `~/.local/bin/blindchess`.

Make sure `~/.local/bin` is in your environment's PATH:
```bash
export PATH="$HOME/.local/bin:$PATH"
```
You can add this line to your `~/.bashrc` or `~/.zshrc`.

---

## Method 2: Development Installation

If you plan to modify or inspect the codebase:
```bash
python3 -m venv .venv
source .venv/bin/activate
pip install --upgrade pip
pip install -e ".[dev]"
```

Run tests to verify the installation:
```bash
pytest tests/ -v
```

---

## Stockfish Installation Details

BlindChess does not require root privileges or sudo to run. If Stockfish is not installed via your system package manager:

### System Package Manager:
```bash
# Ubuntu / Debian / Pop!_OS
sudo apt update && sudo apt install stockfish

# Arch Linux / Manjaro
sudo pacman -S stockfish

# Fedora / RHEL
sudo dnf install stockfish

# openSUSE
sudo zypper install stockfish
```

### User-Level Manual Installation (No Sudo):
```bash
mkdir -p ~/.local/bin
# Download the official universal Linux release from Stockfish:
curl -L https://github.com/official-stockfish/Stockfish/releases/latest/download/stockfish-linux-x86-64-universal.tar.gz -o /tmp/sf.tar.gz
tar -xzf /tmp/sf.tar.gz -C /tmp
cp /tmp/stockfish/stockfish-linux-x86-64-universal ~/.local/bin/stockfish
chmod +x ~/.local/bin/stockfish
rm -rf /tmp/sf.tar.gz /tmp/stockfish
```

---

## Verifying the Installation

Execute:
```bash
./scripts/verify_installation.sh
```
This verifies your CLI launcher, Python module, python-chess library, and Stockfish responsiveness.

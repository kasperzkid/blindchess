#!/usr/bin/env bash
# ==============================================================================
# BlindChess Automated Linux Installer
# Local-First Blindfold Chess & Strategic Training System
# ==============================================================================
set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
BIN_DIR="${HOME}/.local/bin"
DATA_DIR="${HOME}/.local/share/blindchess"
VENV_DIR="${DATA_DIR}/venv"
LAUNCHER="${BIN_DIR}/blindchess"

# ANSI Colors
BOLD="\033[1m"
CYAN="\033[1;36m"
GREEN="\033[1;32m"
YELLOW="\033[1;33m"
RED="\033[1;31m"
MUTED="\033[0;90m"
RESET="\033[0m"

echo -e "${CYAN}======================================================================${RESET}"
echo -e "${BOLD}                     BlindChess Linux Installer                       ${RESET}"
echo -e "${MUTED}     Local-First Blindfold Chess, Strategic Thinking & Drills         ${RESET}"
echo -e "${CYAN}======================================================================${RESET}"
echo ""

# ------------------------------------------------------------------------------
# 1. Detect Package Manager & Distro
# ------------------------------------------------------------------------------
detect_pkg_manager() {
    if command -v apt-get &>/dev/null; then
        echo "apt"
    elif command -v dnf &>/dev/null; then
        echo "dnf"
    elif command -v pacman &>/dev/null; then
        echo "pacman"
    elif command -v zypper &>/dev/null; then
        echo "zypper"
    elif command -v apk &>/dev/null; then
        echo "apk"
    else
        echo "unknown"
    fi
}

PKG_MGR=$(detect_pkg_manager)

# ------------------------------------------------------------------------------
# 2. Check and Install Required System Packages
# ------------------------------------------------------------------------------
echo -e "${BOLD}[1/5] Checking system dependencies...${RESET}"

MISSING_PKGS=()

if ! command -v python3 &>/dev/null; then
    MISSING_PKGS+=("python3")
fi

if ! python3 -c 'import venv' &>/dev/null 2>&1; then
    MISSING_PKGS+=("python3-venv")
fi

if ! command -v curl &>/dev/null && ! command -v wget &>/dev/null; then
    MISSING_PKGS+=("curl")
fi

if ! command -v tar &>/dev/null; then
    MISSING_PKGS+=("tar")
fi

if [ ${#MISSING_PKGS[@]} -gt 0 ]; then
    echo -e "${YELLOW}Missing required tools:${RESET} ${MISSING_PKGS[*]}"
    if [ "$PKG_MGR" != "unknown" ]; then
        echo -e "Attempting to install missing packages via ${BOLD}${PKG_MGR}${RESET}..."
        SUDO_CMD=""
        if [ "$EUID" -ne 0 ]; then
            if command -v sudo &>/dev/null; then
                SUDO_CMD="sudo"
            else
                echo -e "${RED}ERROR: Root/sudo privileges required to install system packages.${RESET}"
                echo -e "Please install manually: ${MISSING_PKGS[*]}"
                exit 1
            fi
        fi

        case "$PKG_MGR" in
            apt)
                $SUDO_CMD apt-get update -y
                $SUDO_CMD apt-get install -y python3 python3-venv python3-pip curl tar
                ;;
            dnf)
                $SUDO_CMD dnf install -y python3 python3-pip curl tar
                ;;
            pacman)
                $SUDO_CMD pacman -Sy --noconfirm python python-pip curl tar
                ;;
            zypper)
                $SUDO_CMD zypper install -y python3 python3-pip curl tar
                ;;
            apk)
                $SUDO_CMD apk add --no-cache python3 py3-pip curl tar
                ;;
        esac
    else
        echo -e "${RED}Unknown package manager. Please manually install: ${MISSING_PKGS[*]}${RESET}"
        exit 1
    fi
else
    echo -e "${GREEN}✓ All core system dependencies found.${RESET}"
fi

# Verify Python 3.10+
PY_VERSION=$(python3 -c 'import sys; print(f"{sys.version_info.major}.{sys.version_info.minor}")')
PY_MAJOR=$(python3 -c 'import sys; print(sys.version_info.major)')
PY_MINOR=$(python3 -c 'import sys; print(sys.version_info.minor)')

if [ "$PY_MAJOR" -lt 3 ] || { [ "$PY_MAJOR" -eq 3 ] && [ "$PY_MINOR" -lt 10 ]; }; then
    echo -e "${RED}ERROR: Python 3.10 or higher is required (found $PY_VERSION).${RESET}"
    exit 1
fi
echo -e "${GREEN}✓ Python version:${RESET} $PY_VERSION"

# ------------------------------------------------------------------------------
# 3. Detect or Install Stockfish Chess Engine
# ------------------------------------------------------------------------------
echo ""
echo -e "${BOLD}[2/5] Checking Stockfish chess engine...${RESET}"
STOCKFISH_FOUND=false
SF_BIN=""

if command -v stockfish &>/dev/null; then
    SF_BIN=$(command -v stockfish)
    STOCKFISH_FOUND=true
elif [ -x "${BIN_DIR}/stockfish" ]; then
    SF_BIN="${BIN_DIR}/stockfish"
    STOCKFISH_FOUND=true
elif [ -x "/usr/games/stockfish" ]; then
    SF_BIN="/usr/games/stockfish"
    STOCKFISH_FOUND=true
fi

if [ "$STOCKFISH_FOUND" = true ]; then
    echo -e "${GREEN}✓ Stockfish located at:${RESET} $SF_BIN"
else
    echo -e "${YELLOW}Stockfish not found on system. Installing Stockfish...${RESET}"
    mkdir -p "${BIN_DIR}"
    
    INSTALLED_VIA_PKG=false
    if command -v sudo &>/dev/null || [ "$EUID" -eq 0 ]; then
        SUDO_CMD=""
        [ "$EUID" -ne 0 ] && SUDO_CMD="sudo"
        case "$PKG_MGR" in
            apt)
                echo "Attempting installation via apt..."
                if $SUDO_CMD apt-get install -y stockfish; then
                    INSTALLED_VIA_PKG=true
                fi
                ;;
            pacman)
                echo "Attempting installation via pacman..."
                if $SUDO_CMD pacman -S --noconfirm stockfish; then
                    INSTALLED_VIA_PKG=true
                fi
                ;;
            dnf)
                echo "Attempting installation via dnf..."
                if $SUDO_CMD dnf install -y stockfish; then
                    INSTALLED_VIA_PKG=true
                fi
                ;;
        esac
    fi

    # Fallback to direct download of official x86_64 binary if package install skipped/failed
    if [ "$INSTALLED_VIA_PKG" = false ]; then
        ARCH=$(uname -m)
        echo "Downloading official Stockfish standalone binary for Linux ($ARCH)..."
        TMP_SF_DIR=$(mktemp -d)
        
        # Determine appropriate build (AVX2 or standard popcnt/sse41)
        SF_URL="https://github.com/official-stockfish/Stockfish/releases/latest/download/stockfish-ubuntu-x86-64-avx2.tar"
        if ! grep -q "avx2" /proc/cpuinfo 2>/dev/null; then
            SF_URL="https://github.com/official-stockfish/Stockfish/releases/latest/download/stockfish-ubuntu-x86-64-sse41-popcnt.tar"
        fi

        DOWNLOAD_SUCCESS=false
        if command -v curl &>/dev/null; then
            if curl -sL "$SF_URL" -o "${TMP_SF_DIR}/stockfish.tar"; then
                DOWNLOAD_SUCCESS=true
            fi
        elif command -v wget &>/dev/null; then
            if wget -qO "${TMP_SF_DIR}/stockfish.tar" "$SF_URL"; then
                DOWNLOAD_SUCCESS=true
            fi
        fi

        if [ "$DOWNLOAD_SUCCESS" = true ]; then
            tar -xf "${TMP_SF_DIR}/stockfish.tar" -C "${TMP_SF_DIR}"
            EXTRACTED_BIN=$(find "${TMP_SF_DIR}" -type f -name "stockfish*" | head -n 1)
            if [ -n "$EXTRACTED_BIN" ]; then
                cp "$EXTRACTED_BIN" "${BIN_DIR}/stockfish"
                chmod +x "${BIN_DIR}/stockfish"
                echo -e "${GREEN}✓ Stockfish successfully installed to ${BIN_DIR}/stockfish${RESET}"
            fi
        else
            echo -e "${YELLOW}Notice: Could not automatically download Stockfish binary.${RESET}"
            echo -e "${MUTED}BlindChess will operate in engine-free mode. You can install stockfish later anytime.${RESET}"
        fi
        rm -rf "${TMP_SF_DIR}"
    fi
fi

# ------------------------------------------------------------------------------
# 4. Create Dedicated Virtual Environment & Install BlindChess
# ------------------------------------------------------------------------------
echo ""
echo -e "${BOLD}[3/5] Setting up dedicated Python virtual environment...${RESET}"
echo -e "Target directory: ${MUTED}${VENV_DIR}${RESET}"

mkdir -p "${DATA_DIR}"
python3 -m venv "${VENV_DIR}"

echo "Installing BlindChess and dependencies..."
"${VENV_DIR}/bin/pip" install --upgrade pip --quiet
"${VENV_DIR}/bin/pip" install "${SCRIPT_DIR}" --quiet

echo -e "${GREEN}✓ Package installed in virtual environment.${RESET}"

# ------------------------------------------------------------------------------
# 5. Create Global Launcher & Configure PATH
# ------------------------------------------------------------------------------
echo ""
echo -e "${BOLD}[4/5] Creating global launcher executable...${RESET}"
mkdir -p "${BIN_DIR}"

cat << 'EOF' > "${LAUNCHER}"
#!/usr/bin/env bash
# BlindChess Global Command Launcher
export PATH="$HOME/.local/bin:$PATH"
exec "$HOME/.local/share/blindchess/venv/bin/blindchess" "$@"
EOF

chmod +x "${LAUNCHER}"
echo -e "${GREEN}✓ Created launcher:${RESET} ${LAUNCHER}"

# Optional symlink in /usr/local/bin if writable or with passwordless sudo
if [ -w "/usr/local/bin" ]; then
    ln -sf "${LAUNCHER}" "/usr/local/bin/blindchess"
    echo -e "${GREEN}✓ Symlinked to /usr/local/bin/blindchess${RESET}"
fi

# Ensure ~/.local/bin is in user PATH
PATH_CONFIGURED=false
if [[ ":$PATH:" == *":$HOME/.local/bin:"* ]]; then
    PATH_CONFIGURED=true
fi

if [ "$PATH_CONFIGURED" = false ]; then
    echo -e "${YELLOW}Adding ${BIN_DIR} to your shell configuration...${RESET}"
    SHELL_CONFIGS=()
    [ -f "${HOME}/.bashrc" ] && SHELL_CONFIGS+=("${HOME}/.bashrc")
    [ -f "${HOME}/.zshrc" ] && SHELL_CONFIGS+=("${HOME}/.zshrc")
    [ -f "${HOME}/.profile" ] && SHELL_CONFIGS+=("${HOME}/.profile")

    for cfg in "${SHELL_CONFIGS[@]}"; do
        if ! grep -q 'export PATH="$HOME/.local/bin:$PATH"' "$cfg" 2>/dev/null; then
            echo 'export PATH="$HOME/.local/bin:$PATH"' >> "$cfg"
            echo -e "${MUTED}Updated $cfg${RESET}"
        fi
    done
fi

# ------------------------------------------------------------------------------
# 6. Verify Installation
# ------------------------------------------------------------------------------
echo ""
echo -e "${BOLD}[5/5] Verifying installation...${RESET}"

if "${LAUNCHER}" --version &>/dev/null; then
    VER=$("${LAUNCHER}" --version)
    echo -e "${GREEN}✓ Verification succeeded!${RESET} (${VER})"
else
    echo -e "${YELLOW}Warning: Verification command failed. Please check launcher permissions.${RESET}"
fi

echo ""
echo -e "${CYAN}======================================================================${RESET}"
echo -e "${GREEN}${BOLD}             BlindChess Successfully Installed!                      ${RESET}"
echo -e "${CYAN}======================================================================${RESET}"
echo -e "You can now run BlindChess from anywhere in your terminal:"
echo ""
echo -e "  ${BOLD}blindchess${RESET}                 # Launch interactive training hub"
echo -e "  ${BOLD}blindchess --mode spatial${RESET}  # Direct launch into Adaptive Spatial Drills"
echo -e "  ${BOLD}blindchess --mode game${RESET}     # Play blindfold sparring against Stockfish"
echo -e "  ${BOLD}blindchess --help${RESET}          # Display all options and commands"
echo ""
if [ "$PATH_CONFIGURED" = false ]; then
    echo -e "${YELLOW}Note: To use 'blindchess' in your current terminal session without logging out:${RESET}"
    echo -e "  ${BOLD}export PATH=\"\$HOME/.local/bin:\$PATH\"${RESET}"
    echo ""
fi
echo -e "${MUTED}To uninstall anytime, simply run: ./uninstall.sh${RESET}"
echo -e "${CYAN}======================================================================${RESET}"

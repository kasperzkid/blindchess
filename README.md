# BlindChess

[![Python](https://img.shields.io/badge/Python-3.10%2B-blue.svg)](https://www.python.org/)
[![Platform](https://img.shields.io/badge/Platform-Linux-orange.svg)](#)
[![Offline First](https://img.shields.io/badge/Architecture-Offline--First-green.svg)](#)
[![Telemetry](https://img.shields.io/badge/Telemetry-Zero-brightgreen.svg)](#)
[![License: MIT](https://img.shields.io/badge/License-MIT-yellow.svg)](LICENSE)

> **A local-first Linux blindfold chess, strategic thinking, and variation training system.**

BlindChess is a terminal-first chess trainer designed to develop two interconnected master skills:
1. **Blindfold Visualization:** The ability to construct and maintain a precise mental representation of the board, piece coordinates, attack lines, and multi-ply variations without looking at a board.
2. **Strategic Calculation Depth:** The ability to formulate positional plans, evaluate candidate moves, recognize threats, and calculate tactical branches based on reasons rather than guessing.

**Core Philosophy:** *Think first. Calculate second. Verify third. Learn from the difference.*

---

## Key Highlights

- **100% Local & Offline-First:** Zero cloud dependencies, zero external APIs, zero online accounts, zero telemetry, and zero background network calls.
- **Pure Terminal Architecture:** Clean, developer-focused, distraction-free terminal user interface (TUI) with responsive box-drawing and ANSI palettes.
- **10-Level Progressive Curriculum:** Guided curriculum moving from basic board coordinates to 8-ply blindfold calculation.
- **9 Independent Skill Profiles:** Independent difficulty ratings for coordinates, square colors, piece movement, spatial relationships, knight routes, multi-piece visualization, position memory, move sequences, and tactical calculation.
- **Adaptive Difficulty Controller:** Mathematical promotion ($\ge 8/10$ clean first attempts across variants) and demotion ($4/5$ conceptual mistakes). Knowledge mastery is kept strictly separate from response speed.
- **Intelligent Adaptive Timers:** Monotonic clock with non-blocking terminal countdown, progress bar, 25% warning, 5s emphasis, and 3 timing modes (*Adaptive*, *Challenge*, *Learning*).
- **Stockfish UCI Integration:** Offline engine sparring, MultiPV candidate evaluation, and automated post-game diagnostic reviews.
- **Variation Tree Explorer:** Step forward/backward, branch independently, analyze with MultiPV, and export to PGN.
- **Strategic Coach & Tactical Blunder Alerts:** Probing positional questions before calculating tactical forcing lines.

---

## Quick Installation (One-Command Script)

Clone the repository and run the automated Linux installer. It detects your distribution package manager, installs any missing build packages, sets up or downloads Stockfish, configures an isolated virtual environment, and installs a global `blindchess` command:

```bash
git clone https://github.com/Kito-99/blindchess.git
cd blindchess
./install.sh
```

Once installed, you can launch BlindChess from any terminal:

```bash
blindchess
```

---

## Manual Installation

If you prefer installing manually into your own Python virtual environment:

### Prerequisites
- Linux operating system (Ubuntu, Debian, Fedora, Arch, openSUSE, etc.)
- Python 3.10+
- Stockfish (recommended for engine sparring; install via `sudo apt install stockfish`, `sudo pacman -S stockfish`, or `sudo dnf install stockfish`)

### Setup
```bash
git clone https://github.com/Kito-99/blindchess.git
cd blindchess

# Create and activate virtual environment
python3 -m venv .venv
source .venv/bin/activate

# Install package in editable development mode
pip install -e .

# Run test suite to verify
pytest tests/ -v
```

---

## Quick Start & Usage

### 1. Interactive Main Menu
Launch the full interactive training terminal:
```bash
blindchess
```

From the main menu, select any of the 12 comprehensive training modules:
- `[1]` Play Game (Blindfold Sparring vs Stockfish or Local 2-Player)
- `[2]` Tactical Exercises (Built-in puzzles & motifs)
- `[3]` Spatial Memory Drills (Adaptive Curriculum & Timed Drills)
- `[4]` Calculation Training (Candidate move evaluation & blunder check)
- `[5]` Strategic Position Coach (Probing positional planning)
- `[6]` Opening Practice (Repertoire recall drills)
- `[7]` Endgame Practice (Fundamental endgames & Syzygy tablebases)
- `[8]` Variation Explorer (Branching tree analysis with MultiPV)
- `[9]` Game Review Mode (Blunder and accuracy diagnostic)
- `[10]` Training Statistics & Analytics (Progress & recommendations)
- `[11]` Settings & Engine Configuration (Depths, profiles, timers)
- `[12]` Help & Documentation

### 2. Direct CLI Launch Modes
You can jump directly into specific training modes:

```bash
blindchess --mode spatial   # Direct launch into Adaptive Spatial Memory Drills
blindchess --mode game      # Start blindfold sparring match vs Stockfish
blindchess --mode tactics   # Launch tactical puzzle training
blindchess --mode strategy  # Strategic position coaching
blindchess --mode review    # Review your latest saved game or imported PGN
blindchess --version        # Check version
blindchess --help           # Display all CLI arguments
```

---

## Adaptive Progression & 10 Curriculum Levels

Blindfold mastery is developed through 10 ordered curriculum stages:

| Level | Focus Area | Description | Base Time |
| :---: | :--- | :--- | :---: |
| **1** | **Board Foundations** | Files, ranks, square colors, coordinate intersections. | 15s |
| **2** | **Piece Movement & Legality** | Legal destinations on empty board vs. real positions with pins/checks. | 20s |
| **3** | **Spatial Relationships** | Line-sharing, Chebyshev (king move) distance, color parity. | 25s |
| **4** | **Basic Knight Routes** | 1-move leaps and 2-hop intermediate routing (`g7` $\to$ `d4`). | 35s |
| **5** | **Multi-Move Routes** | 3- and 4-move knight routes, shortest paths, obstacle navigation. | 45s |
| **6** | **Multiple Pieces** | Attacker/defender counts, mutual attacks, absolute pin recognition. | 45s |
| **7** | **Position Memory** | Memorize static positions, recall probes after board is hidden. | 60s |
| **8** | **Move Sequences** | Mental 3–8 ply variation execution and resulting piece positions. | 75s |
| **9** | **Tactical Visualization** | 2–4 ply forcing combinations, forks, pins, undefended pieces. | 90s |
| **10** | **Advanced Calculation** | Longer 4–8 ply variations, candidate move comparison without sight. | 120s |

### 9 Independent Skill Ratings
Instead of treating chess visualization as a single flat rating, BlindChess independently measures:
1. `coordinates` — Coordinate Recognition
2. `square_colors` — Square-Color Recognition
3. `piece_movement` — Piece Movement & Legality
4. `spatial_relationships` — Spatial Relationships
5. `knight_routes` — Knight-Route Calculation
6. `multi_piece` — Multi-Piece Visualization
7. `position_memory` — Position Memory & Reconstruction
8. `move_sequences` — Move-Sequence Tracking
9. `tactical_calc` — Tactical Visualization & Deep Calculation

---

## Adaptive Timers & Live Countdown

Exercises feature an intelligent countdown timer powered by `time.monotonic()` and non-blocking I/O:
- **Visual Progress Indicator:** `[████████░░] 24s` in Unicode or `[========..]` in ASCII.
- **25% Remaining Warning:** Alerts user in Amber/Yellow when deadline nears (`⏱ [██░░░░░░] 6s ⚠`).
- **Final 5 Seconds Emphasis:** Bold Red alert (`⏱ [░░░░░░░░] 4.2s ! `).
- **Pace Adaptation:**
  - *Consistently Fast (<60% time):* Timer pace tightens gradually down to $0.80\times$ (20% faster).
  - *Slow but Correct (>85% time):* Time limit expands by $+5\%$ up to $1.30\times$.
  - *Timeouts:* Timer expands by $+15\%$ to rebuild comfort.
  - *Fairness Guarantee:* Slow thinkers are **never** demoted in chess difficulty level for slow response times. Difficulty level demotion requires repeated conceptual chess mistakes.

### 3 Timer Modes
Switchable on the fly with shortcut `[t]`:
- **Adaptive Mode (Default):** Dynamic difficulty, complexity scaling, and performance pace adjustments.
- **Challenge Mode:** Strict level-based limits ($0.85\times$), minimal hints, personal best speed tracking.
- **Learning Mode:** Generous time ($1.50\times$), hints freely allowed, focused on understanding.

---

## Interactive Controls & In-Game Commands

During sparring matches, drills, or analysis, use standard algebraic chess notation (SAN like `e4`, `Nf3`, `O-O`) or UCI coordinate notation (`e2e4`, `g1f3`):

| Command | Action |
| :--- | :--- |
| `board` | Peek at the board as an emergency diagnostic reveal (reveals are tracked in stats) |
| `undo` | Take back full turn plies |
| `moves` | Print complete move history of the active game |
| `status` | Display current game status, checks, and material balance |
| `fen` | Print active FEN string |
| `hint` | Request a targeted conceptual hint (does not give away the move) |
| `skip` | Reveal the solution to the current drill |
| `quit` | Exit back cleanly to the previous menu |

---

## Architecture & Project Structure

```
blindchess/
├── install.sh                  # Automated Linux installer (dependencies, stockfish, venv, global bin)
├── uninstall.sh                # Clean uninstaller (removes launchers, venv, optional data purge)
├── pyproject.toml              # Modern Python packaging configuration (PEP 621)
├── src/
│   └── blindchess/
│       ├── adaptive.py         # 10 curriculum levels, 9 skills, adaptive timers & engine
│       ├── analysis.py         # Engine MultiPV evaluation and continuation lines
│       ├── blindfold.py        # 7-stage generators, BFS knight pathfinding with obstacles
│       ├── board_state.py      # Core board management and ASCII/Unicode rendering
│       ├── calculation.py      # Calculation drill evaluation and blunder analysis
│       ├── cli.py              # Command-line entry points and flags
│       ├── config.py           # Configuration manager and profile persistence
│       ├── endgames.py         # Built-in endgames and Syzygy tablebase probing
│       ├── engine_manager.py   # Stockfish discovery, lifecycle, and UCI protocol
│       ├── engine_profiles.py  # Stockfish opponent rating profiles (Beginner to Grandmaster)
│       ├── errors.py           # Typed domain exception hierarchy
│       ├── notation.py         # Move parsing (SAN & UCI), coordinate helpers
│       ├── openings.py         # Built-in opening repertoires and recall trainer
│       ├── paths.py            # XDG Base Directory specification paths
│       ├── persistence.py      # SQLite schema, migrations, data logging, and backups
│       ├── pgn_tools.py        # Robust PGN import, export, and game loading
│       ├── review.py           # Post-game move quality classification (Blunders, Inaccuracies)
│       ├── session.py          # Active session management and telemetry tracking
│       ├── statistics.py       # Performance computation and adaptive recommendations
│       ├── strategy.py         # Positional features evaluation and rationale coach
│       ├── tactics.py          # Tactical puzzle session orchestration
│       ├── terminal_ui.py      # Responsive design system, panels, tables, timed_prompt
│       └── variations.py       # Branching variation tree with MultiPV analysis
└── tests/
    ├── test_adaptive.py        # Independent skill progression, promotions, demotions
    ├── test_adaptive_timer.py  # Base times, complexity scaling, timeouts, pace adaptation
    ├── test_blindfold.py       # BFS knight shortest path, square colors, coordinate tests
    ├── test_board_state.py     # Board initialization, push/undo, material balance
    ├── test_calculation.py     # Blunder checks and evaluation tests
    ├── test_engine_manager.py  # Stockfish discovery and UCI lifecycle
    ├── test_notation.py        # SAN parsing, promotion, illegal move rejection
    ├── test_persistence.py     # Database schema, sessions, backup/restore
    ├── test_pgn_tools.py       # PGN roundtrip export and loading
    ├── test_review.py          # Move classification and review summary
    ├── test_strategy.py        # Positional questions and rationale explanations
    ├── test_terminal_ui.py     # UI rendering, visible length, ANSI palette
    └── test_variations.py      # Independent variation tree branches and PGN export
```

---

## Running the Automated Test Suite

BlindChess includes a comprehensive automated test suite with 100% offline verification across 82 test cases:

```bash
# Run all tests
pytest tests/ -v

# Run adaptive timer tests specifically
pytest tests/test_adaptive_timer.py -v

# Run with test coverage
pytest tests/ --cov=blindchess
```

---

## Uninstallation

To cleanly remove BlindChess from your system:

```bash
./uninstall.sh
```

Options:
- `./uninstall.sh --keep-data`: Removes the application and virtualenv but preserves your training history database.
- `./uninstall.sh --purge`: Completely removes the software, launchers, and user database.

---

## License

BlindChess is free, open-source software released under the [MIT License](LICENSE).

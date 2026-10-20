# BlindChess

**BlindChess** is a local-first, privacy-respecting, Linux terminal application designed to build two interconnected skills:
1. **Blindfold Chess Visualization**: The ability to build and maintain an accurate mental representation of the 64 squares, track piece interactions, and calculate lines without visual board crutches.
2. **Strategic Chess Thinking**: The discipline to evaluate candidate moves, diagnose tactical threats, recognize pawn structure dynamics, and reason independently before consulting computer engines.

**Core Philosophy:** *Think first. Calculate second. Verify third. Learn from the difference.*

---

## Table of Contents

- [Features](#features)
- [System Requirements](#system-requirements)
- [Quick Start Tutorial (5 Minutes)](#quick-start-tutorial-5-minutes)
- [Chess Notation Guide](#chess-notation-guide)
- [Core Concepts & Terminology](#core-concepts--terminology)
- [Stockfish Engine Setup](#stockfish-engine-setup)
- [Training Modes](#training-modes)
  - [1. Blindfold Game](#1-blindfold-game)
  - [2. Spatial Visualization Drills](#2-spatial-visualization-drills)
  - [3. Candidate Calculation Training](#3-candidate-calculation-training)
  - [4. Variation Explorer](#4-variation-explorer)
  - [5. Strategic Position Coach](#5-strategic-position-coach)
  - [6. Tactical Training](#6-tactical-training)
  - [7. Opening Repertoire Practice](#7-opening-repertoire-practice)
  - [8. Endgame Practice & Tablebases](#8-endgame-practice--tablebases)
  - [9. Game Review](#9-game-review)
- [Persistent Storage & Statistics](#persistent-storage--statistics)
- [Command Line Options](#command-line-options)
- [Automated Testing](#automated-testing)
- [Troubleshooting & Limitations](#troubleshooting--limitations)

---

## Features

- **100% Offline & Local-First**: No cloud APIs, no accounts, no telemetry, no background network calls.
- **Authoritative Move Validation**: Full FIDE chess rules backed by `python-chess`.
- **Pure Notation Interface**: Input moves in Standard Algebraic Notation (`e4`, `Nf3`, `Bxc6+`, `O-O`) or coordinate notation (`e2e4`, `g1f3`).
- **Hidden-Board Blindfold Mode**: The board remains invisible by default; optional peek records reveal counts to measure visual dependency.
- **Stockfish UCI Engine Integration**: Automatic discovery, safe process lifecycle, configurable threads, hash limits, and MultiPV multi-line analysis.
- **7 Difficulty Profiles**: Beginner (~1350), Casual (~1500), Intermediate (~1750), Advanced (~2000), Expert (~2300), Full Strength, and Custom.
- **Independent Opponent vs. Analysis Strength**: Spar against an intermediate opponent, then analyze games at grandmaster depth.
- **Grounded Positional Heuristics**: Explanations grounded in center control, development, king exposure, outposts, and pawn structure rather than raw numbers.
- **Post-Game Diagnostics**: Automated classification of inaccuracies, mistakes, blunders, and missed tactical shots.
- **Adaptive Progression**: Explainable recommendation system that proposes leveling up or down based on recent performance.
- **Full PGN & FEN Support**: Export and import games and branching variation trees.
- **XDG Linux Compliance**: Respects `~/.config/blindchess`, `~/.local/share/blindchess`, and `~/.cache/blindchess`.

---

## System Requirements

- **Operating System**: Linux (Ubuntu, Debian, Arch Linux, Fedora, openSUSE, Alpine, etc.).
- **Python**: Python 3.10 or later (tested on Python 3.11, 3.12, 3.14).
- **Chess Engine (Optional)**: Stockfish (recommended for sparring and analysis; the application is fully functional in engine-free mode for drills and two-player games).
- **Terminal**: Any standard terminal emulator or SSH session (UTF-8 supported, with automatic ASCII fallback).

---

## Quick Start Tutorial (5 Minutes)

### Step 1: Install BlindChess
```bash
git clone https://github.com/your-username/blindchess.git
cd blindchess
python3 -m venv .venv
source .venv/bin/activate
pip install -e .
```

### Step 2: Launch Interactive Trainer
```bash
blindchess
```

### Step 3: Play a Blindfold Move
1. Select option `1` (Blindfold Game).
2. Enter your first move: `e4`
3. Engine replies: `Recorded: e5`
4. Enter your development move: `Nf3`
5. If you lose your mental picture of the board, type `board` to peek. Notice that peeks are recorded in your session statistics to track your reliance on visual crutches!
6. Type `quit` when finished.

---

## Chess Notation Guide

BlindChess accepts Standard Algebraic Notation (SAN) and UCI coordinate notation.

| Notation | Meaning | Example |
| :--- | :--- | :--- |
| **Pawn move** | Target square only | `e4`, `d5`, `c4` |
| **N** | Knight | `Nf3`, `Nc6`, `Nbd2` |
| **B** | Bishop | `Bc4`, `Bb5`, `Bg5` |
| **R** | Rook | `Re1`, `Rad1`, `Rc8` |
| **Q** | Queen | `Qd5`, `Qe2`, `Qh4` |
| **K** | King | `Ke2`, `Kf1`, `Kg8` |
| **x** | Capture | `exd5`, `Nxc7`, `Bxf7+` |
| **+** | Check | `Qh4+`, `Bb5+`, `Nxf7+` |
| **#** | Checkmate | `Qh4#`, `Qxf7#`, `Qe8#` |
| **O-O** | Kingside Castling | `O-O` or `0-0` or `o-o` |
| **O-O-O** | Queenside Castling | `O-O-O` or `0-0-0` or `o-o-o` |
| **=Q** | Pawn Promotion | `e8=Q`, `a1=N` |
| **Coordinate** | From-square + To-square | `e2e4`, `g1f3`, `e7e8q` |

---

## Core Concepts & Terminology

- **Ply (Half-Move)**: A single turn played by either White or Black. One full move consists of two plies (White's move followed by Black's reply).
- **Variation**: A concrete branch or hypothetical sequence of moves stemming from a position.
- **Evaluation**: The engine's score estimate for a position from White's perspective (+1.50 means White has an advantage worth roughly 1.5 pawns; -0.80 means Black is ahead). Forced checkmates are indicated as `+M3` (White mates in 3 moves) or `-M2` (Black mates in 2 moves).
- **Principal Variation (PV)**: The optimal sequence of moves calculated by the engine when both sides play their best moves.
- **MultiPV**: An engine feature that computes multiple independent candidate variations simultaneously from the same position.

---

## Stockfish Engine Setup

BlindChess automatically searches for Stockfish in common Linux locations:
- `~/.local/bin/stockfish`
- `/usr/bin/stockfish`
- `/usr/games/stockfish`
- `/usr/local/bin/stockfish`
- Paths specified via the `STOCKFISH_PATH` environment variable or `--engine /path/to/binary`.

### Installing Stockfish on Linux:
- **Ubuntu / Debian**: `sudo apt install stockfish`
- **Arch Linux**: `sudo pacman -S stockfish`
- **Fedora**: `sudo dnf install stockfish`
- **Manual / Non-root**: Download the Linux x86_64 binary from [stockfishchess.org](https://stockfishchess.org/download/) and place it in `~/.local/bin/stockfish`.

If Stockfish is not present, BlindChess operates in **Engine-Free Mode**: legal move validation, spatial exercises, tactical drills, PGN tools, and local two-player practice remain fully functional.

---

## Training Modes

### 1. Blindfold Game
Play against Stockfish or locally against a friend with the board completely hidden.
- Type moves in SAN (`e4`, `Nf3`).
- Commands available during game: `help`, `board` (peek), `moves` (history), `status`, `undo`, `redo`, `save`, `quit`.
- Strict mode (`--strict-blindfold`) locks out the `board` command for rigorous visualization discipline.

### 2. Spatial Visualization Drills
Develop your internal chessboard map across 6 levels:
- **Level 1**: Square color identification (`e4` = light, `d4` = dark) and color complex comparisons.
- **Level 2**: Knight routes (intermediate squares between two points) and bishop diagonal alignment.
- **Level 3**: Mental move sequence tracking (where does a piece land after 6-8 plies?).
- **Level 4-6**: Tactical visualization and multi-ply variation comparison.

### 3. Candidate Calculation Training
- Presents a position without revealing the solution.
- Asks you to identify immediate threats, candidate moves, predicted opponent replies, and estimated evaluation.
- Compares your calculation line against Stockfish MultiPV analysis.
- Flags missed tactical resources (overlooked checkmates, hanging pieces, blunders).

### 4. Variation Explorer
- Interactive branching tree editor.
- Navigate lines (`back`, `forward`, `root`), delete branches, add candidate moves, and inspect MultiPV engine lines.
- Export entire variation trees directly to standard PGN format.

### 5. Strategic Position Coach
- Diagnoses positional features: central square control, piece development, king safety, open files, passed pawns, and isolated pawns.
- Presents structured reasoning questions to guide positional thinking before calculation.

### 6. Tactical Training
- Curated tactical puzzles covering forks, pins, skewers, back-rank mates, deflection, and king attacks.
- Graduated 3-tier hints: conceptual motif -> targeted square/piece -> concrete move.

### 7. Opening Repertoire Practice
- Built-in repertoires (Italian Game, Ruy Lopez, Queen's Gambit Declined, Sicilian Najdorf, Caro-Kann).
- Tests recall move by move; non-judgmentally flags deviations from your prepared repertoire.

### 8. Endgame Practice & Tablebases
- Fundamental theoretical endgames (King + Pawn opposition, Lucena bridge building, Philidor 3rd-rank defense, K+R vs K checkmate).
- Optional Syzygy endgame tablebase support for exact theoretical game-theoretic outcomes (Win/Draw/Loss in N).

### 9. Game Review
- Analyzes completed games ply by ply.
- Classifies each move: *Best / Excellent*, *Good*, *Inaccuracy*, *Mistake*, *Blunder*, *Missed Win*.
- Highlights missed tactical continuations and suggested engine alternatives.

---

## Persistent Storage & Statistics

All data is stored locally in accordance with the Linux XDG specification:
- **Configuration**: `~/.config/blindchess/config.json`
- **Database**: `~/.local/share/blindchess/blindchess.db` (SQLite)
- **Saved PGNs**: `~/.local/share/blindchess/pgn/`
- **Backups**: `~/.local/share/blindchess/backups/`

### Adaptive Difficulty
The statistics subsystem monitors your last 5-10 sessions. If your solve rate exceeds 80% with low board reveals, the system recommends advancing to the next level. If cognitive strain is elevated, it recommends consolidating at a lower level. You always retain manual control.

---

## Command Line Options

```text
usage: blindchess [-h] [--mode {menu,blindfold,play,calculate,variations,strategy,tactics,openings,endgames,review,stats}]
                  [--level {beginner,casual,intermediate,advanced,expert,full_strength}]
                  [--side {white,black,random}] [--engine ENGINE]
                  [--depth DEPTH] [--time TIME] [--multipv MULTIPV]
                  [--threads THREADS] [--hash HASH] [--show-board]
                  [--strict-blindfold] [--ascii] [--config CONFIG]
                  [--data-dir DATA_DIR] [--pgn PGN] [--verbose]
```

### Example Commands:
```bash
# Launch interactive menu
blindchess

# Play blindfold game as Black against Casual opponent
blindchess --mode play --side black --level casual

# Strict blindfold calculation session (no peeking allowed)
blindchess --mode calculate --strict-blindfold

# Explore variations with 3 MultiPV candidate lines
blindchess --mode variations --multipv 3

# Review a saved PGN game
blindchess --mode review --pgn my_game.pgn

# Force ASCII mode on minimal terminal / serial console
blindchess --mode play --ascii
```

---

## Automated Testing

Run the automated test suite:
```bash
pytest tests/ -v
```
The test suite includes 46 comprehensive tests covering SAN parsing, coordinate notation, board state, undo/redo, blindfold visualization, variations, engine communication, tactical hints, SQLite persistence, and PGN round-trips.

---

## Troubleshooting & Limitations

- **Stockfish not recognized**: Verify the binary is marked executable (`chmod +x /path/to/stockfish`) or pass `--engine /path/to/stockfish`.
- **Unicode characters look misaligned**: Run with `--ascii` to force standard ASCII piece rendering.
- **Tablebases**: Tablebase probing requires 3-4-5-6 piece `.rtbw` / `.rtbz` Syzygy files placed in a directory configured under `tablebase_path` in `config.json`.

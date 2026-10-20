# Changelog

All notable changes to BlindChess are documented in this file.

## [1.0.0] - 2026-10-20

### Added
- Complete Linux-first terminal blindfold chess training system.
- Standard Algebraic Notation (SAN) and coordinate notation parsing and legal move validation.
- Internal authoritative chess board state management, move history, and multi-ply undo/redo.
- Stockfish UCI engine integration with automatic discovery and multi-level opponent profiles:
  - Beginner, Casual, Intermediate, Advanced, Expert, Full Strength, Custom.
- MultiPV deep analysis supporting multiple candidate variations, centipawns, and forced mate evaluations.
- Blindfold training engine with hidden-board mechanics, reveal counters, and strict blindfold enforcement.
- Progressive spatial visualization drills (square color, color complexes, knight routes, bishop diagonals, mental move tracking).
- Calculation trainer comparing user candidate moves and predicted replies against Stockfish lines.
- Positional strategic reasoning coach analyzing development, center control, king safety, pawn structures, and undefended pieces.
- Tactical training subsystem with curated benchmark puzzles and graduated hints.
- Opening repertoire practice with deviation tracking and recall drills.
- Endgame practice with opposition, key squares, and optional Syzygy tablebase probing.
- Post-game review categorizing Inaccuracies, Mistakes, Blunders, Missed Wins, and tactical opportunities.
- SQLite local persistence for training history, tactical drills, calculation attempts, and saved games.
- Adaptive difficulty progression evaluating recent performance and explainable level suggestions.
- PGN and FEN import/export with size and safety limits.
- Automated pytest test suite covering notation, board state, variations, blindfold drills, tactics, engine, and persistence.
- Installation, uninstallation, and verification scripts adhering to XDG Linux standards.

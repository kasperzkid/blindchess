# Troubleshooting Guide

Common issues and solutions when running BlindChess on Linux.

---

### 1. "Stockfish engine executable not found"
**Cause:** Stockfish is not in your system PATH or standard Linux binary directories.  
**Solution:**
- Install Stockfish via your package manager (`sudo apt install stockfish` or `sudo pacman -S stockfish`).
- Or specify the exact binary path directly:
  ```bash
  blindchess --engine /path/to/stockfish
  ```
- Or place the binary in `~/.local/bin/stockfish`.

---

### 2. Unicode Chess Symbols Display as Question Marks or Squares
**Cause:** The active terminal emulator does not have a font with chess glyphs (U+2654 to U+265F).  
**Solution:**
- Run BlindChess with the `--ascii` flag:
  ```bash
  blindchess --ascii
  ```
- Or set `"ascii_only": true` in `~/.config/blindchess/config.json`.

---

### 3. Move Entry Fails: "Illegal move in current position"
**Cause:** The move violates chess rules (e.g. king remains in check, piece pinned, pawn cannot jump diagonally without capturing).  
**Solution:**
- In blindfold mode, if you are unsure of the position, type `board` to verify piece locations.
- Verify whose turn it is using `status`.

---

### 4. Pawn Promotion Notation
**Cause:** Attempting to play `e8` or `e7e8` without declaring which piece to promote to.  
**Solution:**
- In SAN: `e8=Q` (or `e8=R`, `e8=B`, `e8=N`).
- In coordinate notation: `e7e8q`.

---

### 5. Engine Stalls or Hangs
**Cause:** Excessively high depth or time limits combined with low CPU resources.  
**Solution:**
- Press `Ctrl+C`. BlindChess intercepts SIGINT cleanly, instructs Stockfish to stop immediately, and safely closes the process without leaving zombie tasks.
- Reduce thinking time or search depth using `--time 1.0 --depth 12`.

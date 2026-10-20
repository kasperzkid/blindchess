# BlindChess User Guide

Welcome to **BlindChess**. This guide details everyday training workflows, commands, and settings.

---

## 1. Navigating the Interface

Launch the interactive main menu:
```bash
blindchess
```
You will be presented with the main menu:
```text
Choose a mode:

 1. Blindfold Game (Board Hidden)
 2. Strength-Based Opponent (Play Stockfish)
 3. Spatial Visualization Drills (Level 1-6)
 4. Calculation Training (Candidate Moves)
 5. Variation Explorer (MultiPV Tree)
 6. Strategic Position Training
 7. Tactical Training (Puzzles & Hints)
 8. Opening Repertoire Practice
 9. Endgame Practice
10. Game Review
11. Training Statistics & Progress
12. Settings
13. Quit
```

---

## 2. In-Game Commands

When playing or solving exercises, the following contextual commands are accepted at any move prompt:

- `help`: Shows available commands and notation examples.
- `board`: Peeks at the current position. (Increments your reveal counter in blindfold mode).
- `moves`: Prints the move history recorded so far.
- `fen`: Displays the active position's FEN string.
- `status`: Displays whose turn it is, check/checkmate condition, and current material balance.
- `undo`: Takes back the last move (or full player+engine turn in play mode).
- `redo`: Replays a previously undone move.
- `hint`: Requests graduated tactical or strategic advice.
- `save`: Saves the ongoing game to SQLite and exports PGN.
- `quit`: Exits back to the menu or shell.

---

## 3. Strict Blindfold Mode

If you wish to prevent yourself from peeking at the board, run:
```bash
blindchess --mode blindfold --strict-blindfold
```
In strict blindfold mode, typing `board` will be rejected with an instructional message.

---

## 4. Reviewing Games

To review a game recorded during your session:
```bash
blindchess --mode review
```
To review an external PGN file:
```bash
blindchess --mode review --pgn /path/to/game.pgn
```
The review subsystem iterates through each move and classifies quality based on centipawn loss and tactical criteria:
- **Best / Excellent**: Difference <= 15 centipawns.
- **Good**: Difference <= 45 centipawns.
- **Inaccuracy**: Concession between 46 and 90 centipawns.
- **Mistake**: Concession between 91 and 200 centipawns.
- **Blunder**: Concession > 200 centipawns.
- **Missed Win**: Overlooking a forced checkmate or winning sequence.

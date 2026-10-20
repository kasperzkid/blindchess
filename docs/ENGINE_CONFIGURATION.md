# Stockfish Engine Configuration & Profiles

BlindChess communicates with Stockfish using the official Universal Chess Interface (UCI) via `python-chess`.

---

## Opponent Profiles

BlindChess separates **opponent strength** (how strong the engine plays against you) from **analysis strength** (how deeply it analyzes positions in the review and variation tools).

| Profile | Skill Level | UCI_LimitStrength | UCI_Elo | Default Depth | Default Thinking Time |
| :--- | :---: | :---: | :---: | :---: | :---: |
| **Beginner** | 1 | True | 1350 | 5 | 0.5s |
| **Casual** | 5 | True | 1500 | 8 | 0.8s |
| **Intermediate** | 10 | True | 1750 | 12 | 1.2s |
| **Advanced** | 15 | True | 2000 | 16 | 2.0s |
| **Expert** | 18 | True | 2300 | 20 | 3.0s |
| **Full Strength** | 20 | False | Max | Unlimited | 3.0s |

> [!NOTE]
> Elo ratings configured via `UCI_Elo` are calibrated engine estimates and do not guarantee an exact human FIDE rating equivalence across all openings and time controls.

---

## MultiPV Analysis

MultiPV allows Stockfish to compute and output multiple candidate moves simultaneously:
```bash
blindchess --mode variations --multipv 3
```
Each line displays:
- Rank (1 = best move).
- First move in SAN.
- Evaluation score (+ = White advantage, - = Black advantage, +M = mate in N).
- Calculation depth (`d=N`).
- Principal variation continuation moves.

---

## Resource Management

BlindChess is designed for low CPU and memory footprint:
- **Default Threads**: 1 (prevents freezing the host system during play).
- **Default Hash Memory**: 64 MB.
- **Engine Process**: Only 1 Stockfish process is spawned at a time and is cleanly terminated upon exit.

Advanced users can adjust these via command-line flags or `config.json`:
```bash
blindchess --threads 4 --hash 256 --depth 20
```

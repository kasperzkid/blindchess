# BlindChess Training Methodology

*Think first. Calculate second. Verify third. Learn from the difference.*

Most chess software immediately displays arrows, engine evaluations, and visual highlights. While convenient, this creates **cognitive dependency**: the player learns to react to visual cues rather than formulating mental models.

BlindChess is engineered around intentional cognitive friction.

---

## The 4 Pillars of Blindfold Mastery

### Pillar 1: Spatial Memory & Color Complexes
Before calculating variations, a player must know the chessboard geometry intuitively:
- **Square Color Awareness**: Knowing without hesitation whether `c6`, `f3`, `g4`, and `d7` are dark or light squares.
- **Diagonal Trajectories**: Recognizing that a light-squared bishop on `f1` controls `a6-f1` and `h3-c8`.
- **Knight Leaps**: Calculating knight paths by visualizing the 8 possible L-shaped landing spots.

BlindChess provides **Level 1 and Level 2 Spatial Drills** to cement this automatic recognition.

### Pillar 2: Mental Piece Tracking
When moves like `1. e4 e5 2. Nf3 Nc6 3. Bb5 a6 4. Ba4 Nf6` are played, the light-squared bishop has moved twice (`f1 -> b5 -> a4`).
- In **Level 3 Drills**, you follow the moves mentally and identify piece locations, pinned pieces, and open squares without looking at a board.

### Pillar 3: Candidate Move Discipline
Amateur players frequently calculate a single move, fall in love with it, and play it without surveying alternatives.
- The **Calculation Trainer** forces you to explicitly list:
  1. Opponent's immediate threats.
  2. Your candidate move.
  3. Opponent's strongest reply.
  4. Your evaluation.
Only then does the engine reveal its multi-line assessment.

### Pillar 4: Grounded Strategic Understanding
Stockfish evaluates positions numerically (e.g. `+1.85`), but humans think in plans and relationships:
- Center control (`d4`, `e4`, `d5`, `e5`).
- Minor piece development and open files.
- King safety and pawn shields.
- Structural weaknesses (isolated, backward, and doubled pawns).
- Undefended piece vulnerabilities.

The **Strategic Thinking Coach** asks structured diagnostic questions to train positional intuition.

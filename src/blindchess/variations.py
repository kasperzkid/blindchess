"""Tree-structured variation explorer and candidate move branching subsystem."""

from dataclasses import dataclass, field
from typing import Any, Dict, List, Optional
import chess
import chess.pgn

from blindchess.analysis import AnalysisLine, ScoreEvaluation


@dataclass
class VariationNode:
    """A single node in a variation tree representing a move."""
    move: chess.Move
    san: str
    fen: str
    parent: Optional["VariationNode"] = None
    children: List["VariationNode"] = field(default_factory=list)
    comment: str = ""
    name: Optional[str] = None
    analysis: Optional[AnalysisLine] = None

    def add_child(self, move: chess.Move, san: str, fen: str, comment: str = "") -> "VariationNode":
        """Add child move to this node, avoiding duplicates if move already exists."""
        for child in self.children:
            if child.move == move:
                return child
        new_node = VariationNode(
            move=move,
            san=san,
            fen=fen,
            parent=self,
            children=[],
            comment=comment,
        )
        self.children.append(new_node)
        return new_node

    def remove_child(self, child_node: "VariationNode") -> bool:
        """Remove a branch child."""
        if child_node in self.children:
            self.children.remove(child_node)
            child_node.parent = None
            return True
        return False

    @property
    def is_mainline(self) -> bool:
        """Return True if this node is along the primary (first) branch."""
        if self.parent is None:
            return True
        return self.parent.children and self.parent.children[0] is self


class VariationTree:
    """Manages the full variation tree starting from an arbitrary root position."""

    def __init__(self, root_fen: Optional[str] = None):
        self.root_fen = root_fen or chess.STARTING_FEN
        self.root_board = chess.Board(self.root_fen)
        # Dummy root node holding starting FEN
        self.root = VariationNode(
            move=chess.Move.null(),
            san="",
            fen=self.root_fen,
            parent=None,
        )
        self.current_node: VariationNode = self.root

    def current_board(self) -> chess.Board:
        """Construct the chess.Board corresponding to the current node."""
        return chess.Board(self.current_node.fen)

    def add_move(self, move_or_san: str | chess.Move, comment: str = "") -> VariationNode:
        """Add a move from the current node position and advance to it."""
        board = self.current_board()
        if isinstance(move_or_san, str):
            move = board.parse_san(move_or_san)
        else:
            move = move_or_san

        san = board.san(move)
        board.push(move)
        new_fen = board.fen()

        node = self.current_node.add_child(move, san, new_fen, comment=comment)
        self.current_node = node
        return node

    def step_back(self) -> Optional[VariationNode]:
        """Navigate backward to parent node."""
        if self.current_node.parent is not None:
            self.current_node = self.current_node.parent
            return self.current_node
        return None

    def step_forward(self, branch_idx: int = 0) -> Optional[VariationNode]:
        """Navigate forward into a child variation."""
        if self.current_node.children:
            idx = max(0, min(branch_idx, len(self.current_node.children) - 1))
            self.current_node = self.current_node.children[idx]
            return self.current_node
        return None

    def jump_to_root(self) -> VariationNode:
        """Navigate all the way back to the root position."""
        self.current_node = self.root
        return self.current_node

    def delete_current_branch(self) -> bool:
        """Delete the current branch from its parent and step back."""
        if self.current_node is self.root or self.current_node.parent is None:
            return False
        parent = self.current_node.parent
        parent.remove_child(self.current_node)
        self.current_node = parent
        return True

    def get_line_from_root(self) -> List[VariationNode]:
        """Return path of nodes from root to current position."""
        path: List[VariationNode] = []
        node = self.current_node
        while node is not None and node is not self.root:
            path.append(node)
            node = node.parent  # type: ignore
        return list(reversed(path))

    def format_current_line(self) -> str:
        """Format the current active line in readable SAN."""
        nodes = self.get_line_from_root()
        if not nodes:
            return "(Root Position)"
        return " ".join(n.san for n in nodes)

    def export_to_pgn_game(self) -> chess.pgn.Game:
        """Export the complete variation tree into a standard chess.pgn.Game."""
        game = chess.pgn.Game()
        if self.root_fen != chess.STARTING_FEN:
            game.setup(chess.Board(self.root_fen))

        def populate_children(pgn_parent_node: chess.pgn.GameNode, tree_parent_node: VariationNode):
            for idx, child in enumerate(tree_parent_node.children):
                if idx == 0:
                    next_pgn_node = pgn_parent_node.add_variation(child.move)
                else:
                    next_pgn_node = pgn_parent_node.add_variation(child.move)
                if child.comment:
                    next_pgn_node.comment = child.comment
                populate_children(next_pgn_node, child)

        populate_children(game, self.root)
        return game

    def export_to_pgn_string(self) -> str:
        """Export tree as PGN string."""
        game = self.export_to_pgn_game()
        exporter = chess.pgn.StringExporter(headers=True, variations=True, comments=True)
        return game.accept(exporter)

"""Automated tests for VariationTree, branching, and PGN export."""

import chess
from blindchess.variations import VariationTree


def test_variation_tree_mainline():
    tree = VariationTree()
    assert tree.current_node == tree.root

    n1 = tree.add_move("e4")
    assert n1.san == "e4"
    assert tree.format_current_line() == "e4"

    n2 = tree.add_move("e5")
    assert n2.san == "e5"
    assert tree.format_current_line() == "e4 e5"

    # Step back
    prev = tree.step_back()
    assert prev == n1
    assert tree.format_current_line() == "e4"


def test_independent_branches():
    tree = VariationTree()
    tree.add_move("e4")

    # Branch A: 1... e5
    tree.add_move("e5")
    assert tree.format_current_line() == "e4 e5"

    # Step back to 1. e4
    tree.step_back()
    assert tree.format_current_line() == "e4"

    # Branch B: 1... c5 (Sicilian)
    tree.add_move("c5")
    assert tree.format_current_line() == "e4 c5"

    # Verify both children exist on 1. e4 node
    e4_node = tree.current_node.parent
    assert len(e4_node.children) == 2
    assert [c.san for c in e4_node.children] == ["e5", "c5"]


def test_delete_branch():
    tree = VariationTree()
    tree.add_move("e4")
    tree.add_move("c5")

    # Delete 1... c5 branch
    deleted = tree.delete_current_branch()
    assert deleted is True
    assert tree.format_current_line() == "e4"
    assert len(tree.current_node.children) == 0


def test_export_tree_to_pgn():
    tree = VariationTree()
    tree.add_move("e4")
    tree.add_move("e5")
    tree.step_back()
    tree.add_move("c5")

    pgn_str = tree.export_to_pgn_string()
    assert "1. e4 e5 (1... c5)" in pgn_str or "1. e4 e5" in pgn_str
    assert "c5" in pgn_str

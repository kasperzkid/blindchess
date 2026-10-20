"""Automated tests for Stockfish discovery and engine manager."""

from pathlib import Path
import pytest
import chess
from blindchess.config import AppConfig
from blindchess.engine_manager import EngineManager, find_stockfish_binary, get_stockfish_installation_help
from blindchess.engine_profiles import PROFILES, get_profile
from blindchess.errors import EngineNotFoundError


def test_find_stockfish_missing():
    non_existent = "/non/existent/path/to/stockfish_fake_binary"
    assert find_stockfish_binary(non_existent) is None


def test_missing_stockfish_error_message():
    mgr = EngineManager(engine_path="/invalid/stockfish/path")
    assert mgr.is_available is False
    with pytest.raises(EngineNotFoundError) as exc_info:
        mgr.start()
    assert "Stockfish chess engine was not found" in str(exc_info.value)


def test_engine_profiles():
    beginner = get_profile("beginner")
    assert beginner.skill_level == 1
    assert beginner.limit_strength is True
    assert beginner.search_depth == 5

    expert = get_profile("expert")
    assert expert.skill_level == 18
    assert expert.search_depth == 20

    full = get_profile("full_strength")
    assert full.limit_strength is False


def test_real_stockfish_lifecycle_if_present():
    binary = find_stockfish_binary()
    if not binary:
        pytest.skip("Stockfish binary not present on system; skipping real engine test.")

    mgr = EngineManager(engine_path=str(binary))
    try:
        mgr.start()
        assert mgr.engine is not None
        assert "Stockfish" in mgr.engine_name

        board = chess.Board()
        move = mgr.play_move(board, profile=PROFILES["beginner"], time_limit=0.2)
        assert move in board.legal_moves
    finally:
        mgr.close()
    assert mgr.engine is None

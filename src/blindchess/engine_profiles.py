"""Engine playing strength profiles and analysis configurations."""

from dataclasses import dataclass
from typing import Any, Dict, Optional


@dataclass
class EngineProfile:
    """Documented configuration for an engine opponent or analysis session."""
    name: str
    description: str
    skill_level: int              # 0 to 20 (UCI "Skill Level")
    limit_strength: bool          # UCI_LimitStrength
    uci_elo: Optional[int]        # UCI_Elo (if UCI_LimitStrength is True)
    search_depth: Optional[int]   # Depth limit for move calculation
    time_limit: float             # Seconds to think per move
    multipv: int = 1              # Number of principal variations

    def get_uci_options(self, supported_options: Dict[str, Any]) -> Dict[str, Any]:
        """Construct dictionary of UCI options supported by the running engine."""
        options: Dict[str, Any] = {}

        if "Skill Level" in supported_options:
            options["Skill Level"] = self.skill_level

        if self.limit_strength and "UCI_LimitStrength" in supported_options:
            options["UCI_LimitStrength"] = True
            if self.uci_elo and "UCI_Elo" in supported_options:
                elo_opt = supported_options["UCI_Elo"]
                # Bound elo within engine's supported min/max
                min_elo = getattr(elo_opt, "min", 1320)
                max_elo = getattr(elo_opt, "max", 3190)
                bounded_elo = max(min_elo, min(self.uci_elo, max_elo))
                options["UCI_Elo"] = bounded_elo
        elif "UCI_LimitStrength" in supported_options:
            options["UCI_LimitStrength"] = False

        if "MultiPV" in supported_options and self.multipv > 1:
            options["MultiPV"] = self.multipv

        return options


PROFILES: Dict[str, EngineProfile] = {
    "beginner": EngineProfile(
        name="Beginner",
        description="Low tactical vision, occasional oversights, fast moves (~1350 Elo).",
        skill_level=1,
        limit_strength=True,
        uci_elo=1350,
        search_depth=5,
        time_limit=0.5,
    ),
    "casual": EngineProfile(
        name="Casual",
        description="Solid fundamental moves with moderate tactical blindspots (~1500 Elo).",
        skill_level=5,
        limit_strength=True,
        uci_elo=1500,
        search_depth=8,
        time_limit=0.8,
    ),
    "intermediate": EngineProfile(
        name="Intermediate",
        description="Balanced club player strength (~1750 Elo). Punishes obvious errors.",
        skill_level=10,
        limit_strength=True,
        uci_elo=1750,
        search_depth=12,
        time_limit=1.2,
    ),
    "advanced": EngineProfile(
        name="Advanced",
        description="Strong club / tournament player (~2000 Elo). Sharp tactical calculation.",
        skill_level=15,
        limit_strength=True,
        uci_elo=2000,
        search_depth=16,
        time_limit=2.0,
    ),
    "expert": EngineProfile(
        name="Expert",
        description="Master level play (~2300 Elo). Deep tactical and positional awareness.",
        skill_level=18,
        limit_strength=True,
        uci_elo=2300,
        search_depth=20,
        time_limit=3.0,
    ),
    "full_strength": EngineProfile(
        name="Full Strength",
        description="Unrestricted grandmaster/supercomputer engine strength.",
        skill_level=20,
        limit_strength=False,
        uci_elo=None,
        search_depth=None,
        time_limit=3.0,
    ),
}


def get_profile(name_or_key: str) -> EngineProfile:
    """Retrieve engine profile by name or key (case-insensitive)."""
    key = name_or_key.strip().lower().replace(" ", "_").replace("-", "_")
    if key in PROFILES:
        return PROFILES[key]
    # Fallback to intermediate
    return PROFILES["intermediate"]

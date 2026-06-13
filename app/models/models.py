from dataclasses import dataclass, field
from typing import Optional, List, Dict, Any, Tuple
from enum import Enum


class TournamentPhase(str, Enum):
    SETUP = "setup"
    SWISS = "swiss"
    PLAYOFF = "playoff"
    COMPLETED = "completed"


class TeamStatus(str, Enum):
    ACTIVE = "active"
    ADVANCED = "advanced"
    ELIMINATED = "eliminated"


class MatchStatus(str, Enum):
    PENDING = "pending"
    COMPLETED = "completed"


class RoundStatus(str, Enum):
    PENDING = "pending"
    IN_PROGRESS = "in_progress"
    COMPLETED = "completed"


class BracketRound(str, Enum):
    UPPER_QUARTER = "upper_quarter"
    UPPER_SEMI = "upper_semi"
    UPPER_FINAL = "upper_final"
    LOWER_ROUND1 = "lower_round1"
    LOWER_ROUND2 = "lower_round2"
    LOWER_QUARTER = "lower_quarter"
    LOWER_SEMI = "lower_semi"
    LOWER_FINAL = "lower_final"
    GRAND_FINAL = "grand_final"
    GRAND_FINAL_RESET = "grand_final_reset"


@dataclass
class Tournament:
    id: Optional[int] = None
    name: str = ""
    phase: TournamentPhase = TournamentPhase.SETUP
    current_round: int = 0
    swiss_format: str = "bo1"
    playoff_format: str = "bo3"
    advance_wins: int = 3
    eliminate_losses: int = 3


@dataclass
class Team:
    id: Optional[int] = None
    tournament_id: int = 0
    name: str = ""
    seed: int = 0
    wins: int = 0
    losses: int = 0
    status: TeamStatus = TeamStatus.ACTIVE
    has_bye: int = 0
    eliminated_at_round: Optional[int] = None

    @property
    def match_count(self) -> int:
        return self.wins + self.losses

    @property
    def win_rate(self) -> float:
        if self.match_count == 0:
            return 0.0
        return self.wins / self.match_count


@dataclass
class TeamStanding:
    team: Team
    buchholz: float = 0.0
    median_buchholz: float = 0.0
    head_to_head_wins: int = 0
    opponent_win_rate: float = 0.0
    rank: int = 0
    opponents: List[int] = field(default_factory=list)
    scores_for: int = 0
    scores_against: int = 0


@dataclass
class Match:
    id: Optional[int] = None
    tournament_id: int = 0
    round_id: int = 0
    match_number: int = 0
    team1_id: Optional[int] = None
    team2_id: Optional[int] = None
    team1_score: int = 0
    team2_score: int = 0
    winner_id: Optional[int] = None
    status: MatchStatus = MatchStatus.PENDING
    is_bye: bool = False
    bracket_side: Optional[str] = None
    bracket_round: Optional[str] = None
    next_match_id: Optional[int] = None
    next_match_slot: Optional[int] = None


@dataclass
class Round:
    id: Optional[int] = None
    tournament_id: int = 0
    round_number: int = 0
    phase: str = ""
    format: str = ""
    status: RoundStatus = RoundStatus.PENDING


@dataclass
class Pairing:
    team1_id: Optional[int]
    team2_id: Optional[int]
    is_bye: bool = False

    def to_tuple(self) -> Tuple[Optional[int], Optional[int]]:
        return (self.team1_id, self.team2_id)


@dataclass
class BracketNode:
    match_id: Optional[int]
    bracket_round: str
    bracket_side: str
    position: int
    team1_id: Optional[int] = None
    team2_id: Optional[int] = None
    winner_id: Optional[int] = None
    children: List["BracketNode"] = field(default_factory=list)
    parent: Optional["BracketNode"] = None

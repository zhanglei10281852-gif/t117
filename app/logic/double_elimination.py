from typing import List, Dict, Optional, Tuple
from dataclasses import dataclass, field
import math
from app.models.models import Team, BracketNode, BracketRound, Match
from app.database.crud_match import get_match, update_match_teams


@dataclass
class BracketMatchInfo:
    bracket_round: str
    bracket_side: str
    position: int
    team1_seed: Optional[int] = None
    team2_seed: Optional[int] = None
    source1_type: Optional[str] = None
    source1_round: Optional[str] = None
    source1_position: Optional[int] = None
    source2_type: Optional[str] = None
    source2_round: Optional[str] = None
    source2_position: Optional[int] = None
    winner_to_round: Optional[str] = None
    winner_to_position: Optional[int] = None
    winner_to_slot: Optional[int] = None
    loser_to_round: Optional[str] = None
    loser_to_position: Optional[int] = None
    loser_to_slot: Optional[int] = None


class DoubleEliminationBracket:
    def __init__(self, team_count: int):
        self.team_count = team_count
        self.upper_round_count = 0
        self.lower_round_count = 0
        self._calculate_round_counts()
        self.bracket_structure: List[BracketMatchInfo] = []
        self._match_lookup: Dict[Tuple[str, str, int], BracketMatchInfo] = {}

    def _calculate_round_counts(self) -> None:
        if self.team_count < 2:
            raise ValueError("淘汰赛至少需要2支队伍")
        self.upper_round_count = math.ceil(math.log2(self.team_count))
        self.lower_round_count = self.upper_round_count * 2 - 2

    def _get_upper_round_name(self, round_idx: int) -> str:
        total_upper = self.upper_round_count
        if round_idx == total_upper - 1:
            return BracketRound.UPPER_FINAL.value
        elif round_idx == total_upper - 2:
            return BracketRound.UPPER_SEMI.value
        elif round_idx == total_upper - 3:
            return BracketRound.UPPER_QUARTER.value
        else:
            return f"upper_round_{round_idx + 1}"

    def _get_lower_round_name(self, round_idx: int) -> str:
        total_lower = self.lower_round_count
        if round_idx == total_lower - 1:
            return BracketRound.LOWER_FINAL.value
        elif round_idx == total_lower - 2:
            return BracketRound.LOWER_SEMI.value
        elif round_idx == total_lower - 3:
            return BracketRound.LOWER_QUARTER.value
        elif round_idx == 0:
            return BracketRound.LOWER_ROUND1.value
        elif round_idx == 1:
            return BracketRound.LOWER_ROUND2.value
        else:
            return f"lower_round_{round_idx + 1}"

    def generate_bracket_structure(self) -> List[BracketMatchInfo]:
        self.bracket_structure = []
        self._match_lookup = {}
        next_power_of_2 = int(math.pow(2, self.upper_round_count))
        byes_needed = next_power_of_2 - self.team_count
        seeds = list(range(1, self.team_count + 1))

        upper_matches_per_round = []
        for r in range(self.upper_round_count):
            matches_in_round = next_power_of_2 // (2 ** (r + 1))
            upper_matches_per_round.append(matches_in_round)

        lower_matches_per_round = []
        for k in range(self.lower_round_count):
            if k == 0:
                matches = upper_matches_per_round[0] // 2
            elif k % 2 == 1:
                matches = lower_matches_per_round[k - 1]
            else:
                matches = lower_matches_per_round[k - 1] // 2
            lower_matches_per_round.append(matches)

        first_round_seeds = self._generate_first_round_pairings(seeds, byes_needed)

        for pos in range(upper_matches_per_round[0]):
            round_name = self._get_upper_round_name(0)
            s1, s2 = first_round_seeds[pos]
            info = BracketMatchInfo(
                bracket_round=round_name,
                bracket_side="upper",
                position=pos,
                team1_seed=s1,
                team2_seed=s2
            )
            self._add_match_info(info)

        for r in range(1, self.upper_round_count):
            round_name = self._get_upper_round_name(r)
            prev_round = self._get_upper_round_name(r - 1)
            matches_in_round = upper_matches_per_round[r]
            for pos in range(matches_in_round):
                info = BracketMatchInfo(
                    bracket_round=round_name,
                    bracket_side="upper",
                    position=pos,
                    source1_type="winner",
                    source1_round=prev_round,
                    source1_position=pos * 2,
                    source2_type="winner",
                    source2_round=prev_round,
                    source2_position=pos * 2 + 1
                )
                self._add_match_info(info)

        for k in range(self.lower_round_count):
            round_name = self._get_lower_round_name(k)
            matches_in_round = lower_matches_per_round[k]

            for pos in range(matches_in_round):
                info = BracketMatchInfo(
                    bracket_round=round_name,
                    bracket_side="lower",
                    position=pos
                )

                if k == 0:
                    upper_rd = self._get_upper_round_name(0)
                    info.source1_type = "loser"
                    info.source1_round = upper_rd
                    info.source1_position = pos * 2
                    info.source2_type = "loser"
                    info.source2_round = upper_rd
                    info.source2_position = pos * 2 + 1
                elif k % 2 == 1:
                    upper_r = (k + 1) // 2
                    upper_rd = self._get_upper_round_name(upper_r)
                    prev_lower = self._get_lower_round_name(k - 1)
                    info.source1_type = "loser"
                    info.source1_round = upper_rd
                    info.source1_position = pos
                    info.source2_type = "winner"
                    info.source2_round = prev_lower
                    info.source2_position = pos
                else:
                    prev_lower = self._get_lower_round_name(k - 1)
                    info.source1_type = "winner"
                    info.source1_round = prev_lower
                    info.source1_position = pos * 2
                    info.source2_type = "winner"
                    info.source2_round = prev_lower
                    info.source2_position = pos * 2 + 1

                self._add_match_info(info)

        grand_final = BracketMatchInfo(
            bracket_round=BracketRound.GRAND_FINAL.value,
            bracket_side="final",
            position=0,
            source1_type="winner",
            source1_round=BracketRound.UPPER_FINAL.value,
            source1_position=0,
            source2_type="winner",
            source2_round=BracketRound.LOWER_FINAL.value,
            source2_position=0
        )
        self._add_match_info(grand_final)

        grand_final_reset = BracketMatchInfo(
            bracket_round=BracketRound.GRAND_FINAL_RESET.value,
            bracket_side="final",
            position=0,
            source1_type="winner",
            source1_round=BracketRound.GRAND_FINAL.value,
            source1_position=0,
            source2_type="loser",
            source2_round=BracketRound.GRAND_FINAL.value,
            source2_position=0
        )
        self._add_match_info(grand_final_reset)

        self._set_progression_paths(upper_matches_per_round, lower_matches_per_round)

        return self.bracket_structure

    def _generate_first_round_pairings(self, seeds: List[int], byes: int) -> List[Tuple[Optional[int], Optional[int]]]:
        if byes == 0:
            return self._standard_pairing(seeds)

        byes_to_top = []
        for i in range(byes):
            byes_to_top.append((seeds[i], None))

        remaining_seeds = seeds[byes:]
        pairings = self._standard_pairing(remaining_seeds)

        return byes_to_top + pairings

    def _standard_pairing(self, seeds: List[int]) -> List[Tuple[int, int]]:
        n = len(seeds)
        if n == 0:
            return []
        if n == 2:
            return [(seeds[0], seeds[1])]

        sorted_seeds = sorted(seeds)
        half = n // 2
        top = sorted_seeds[:half]
        bottom = sorted_seeds[half:]
        bottom_reversed = bottom[::-1]

        pairings = []
        for i in range(half):
            pairings.append((top[i], bottom_reversed[i]))

        return pairings

    def _add_match_info(self, info: BracketMatchInfo) -> None:
        self.bracket_structure.append(info)
        key = (info.bracket_round, info.bracket_side, info.position)
        self._match_lookup[key] = info

    def _set_progression_paths(self, upper_counts: List[int], lower_counts: List[int]) -> None:
        for r in range(self.upper_round_count - 1):
            curr_round = self._get_upper_round_name(r)
            next_round = self._get_upper_round_name(r + 1)
            matches_in_curr = upper_counts[r]

            for pos in range(matches_in_curr):
                info = self._get_match(curr_round, "upper", pos)
                if info:
                    info.winner_to_round = next_round
                    info.winner_to_position = pos // 2
                    info.winner_to_slot = pos % 2

                    if r == 0:
                        loser_k = 0
                    else:
                        loser_k = 2 * r - 1
                    
                    if loser_k < self.lower_round_count:
                        loser_round = self._get_lower_round_name(loser_k)
                        info.loser_to_round = loser_round
                        if r == 0:
                            info.loser_to_position = pos // 2
                            info.loser_to_slot = pos % 2
                        else:
                            info.loser_to_position = pos
                            info.loser_to_slot = 0

        upper_final = self._get_match(BracketRound.UPPER_FINAL.value, "upper", 0)
        if upper_final:
            upper_final.winner_to_round = BracketRound.GRAND_FINAL.value
            upper_final.winner_to_position = 0
            upper_final.winner_to_slot = 0
            upper_final.loser_to_round = BracketRound.LOWER_FINAL.value
            upper_final.loser_to_position = 0
            upper_final.loser_to_slot = 0

        for k in range(self.lower_round_count - 1):
            curr_round = self._get_lower_round_name(k)
            next_round = self._get_lower_round_name(k + 1)
            matches_in_curr = lower_counts[k]

            for pos in range(matches_in_curr):
                info = self._get_match(curr_round, "lower", pos)
                if info:
                    info.winner_to_round = next_round
                    if k % 2 == 0:
                        info.winner_to_position = pos
                        info.winner_to_slot = 1
                    else:
                        info.winner_to_position = pos // 2
                        info.winner_to_slot = pos % 2

        lower_final = self._get_match(BracketRound.LOWER_FINAL.value, "lower", 0)
        if lower_final:
            lower_final.winner_to_round = BracketRound.GRAND_FINAL.value
            lower_final.winner_to_position = 0
            lower_final.winner_to_slot = 1

        grand_final = self._get_match(BracketRound.GRAND_FINAL.value, "final", 0)
        if grand_final:
            grand_final.winner_to_round = BracketRound.GRAND_FINAL_RESET.value
            grand_final.winner_to_position = 0
            grand_final.winner_to_slot = 0
            grand_final.loser_to_round = BracketRound.GRAND_FINAL_RESET.value
            grand_final.loser_to_position = 0
            grand_final.loser_to_slot = 1

    def _get_match(self, bracket_round: str, bracket_side: str, position: int) -> Optional[BracketMatchInfo]:
        return self._match_lookup.get((bracket_round, bracket_side, position))

    def get_match_infos_by_round(self, bracket_round: str) -> List[BracketMatchInfo]:
        return [m for m in self.bracket_structure if m.bracket_round == bracket_round]

    def get_all_round_names(self) -> List[str]:
        rounds = []
        for r in range(self.upper_round_count):
            rounds.append(self._get_upper_round_name(r))
        for r in range(self.lower_round_count):
            rounds.append(self._get_lower_round_name(r))
        rounds.append(BracketRound.GRAND_FINAL.value)
        rounds.append(BracketRound.GRAND_FINAL_RESET.value)
        return rounds

    def get_round_display_name(self, round_name: str) -> str:
        display_names = {
            BracketRound.UPPER_QUARTER.value: "胜者组 四分之一决赛",
            BracketRound.UPPER_SEMI.value: "胜者组 半决赛",
            BracketRound.UPPER_FINAL.value: "胜者组 决赛",
            BracketRound.LOWER_ROUND1.value: "败者组 第一轮",
            BracketRound.LOWER_ROUND2.value: "败者组 第二轮",
            BracketRound.LOWER_QUARTER.value: "败者组 四分之一决赛",
            BracketRound.LOWER_SEMI.value: "败者组 半决赛",
            BracketRound.LOWER_FINAL.value: "败者组 决赛",
            BracketRound.GRAND_FINAL.value: "总决赛",
            BracketRound.GRAND_FINAL_RESET.value: "总决赛 重赛",
        }

        if round_name.startswith("upper_round_"):
            idx = int(round_name.split("_")[-1])
            return f"胜者组 第{idx}轮"
        if round_name.startswith("lower_round_"):
            idx = int(round_name.split("_")[-1])
            return f"败者组 第{idx}轮"

        return display_names.get(round_name, round_name)


class BracketProgression:
    @staticmethod
    def advance_winner(match: Match, all_matches: Dict[str, Match],
                       bracket_structure: List[BracketMatchInfo],
                       team_id: int, is_winner: bool) -> Optional[int]:
        match_info = None
        for info in bracket_structure:
            if (info.bracket_round == match.bracket_round
                and info.bracket_side == match.bracket_side
                and info.position == match.match_number):
                match_info = info
                break

        if not match_info:
            return None

        if is_winner:
            target_round = match_info.winner_to_round
            target_pos = match_info.winner_to_position
            target_slot = match_info.winner_to_slot
        else:
            target_round = match_info.loser_to_round
            target_pos = match_info.loser_to_position
            target_slot = match_info.loser_to_slot

        if not target_round or target_pos is None:
            return None

        target_match_key = f"{target_round}_{target_pos}"
        target_match = all_matches.get(target_match_key)

        if target_match and target_match.status.value == "pending":
            latest_match = get_match(target_match.id)
            if latest_match and latest_match.status.value == "pending":
                if target_slot == 0:
                    update_match_teams(latest_match.id, team_id, latest_match.team2_id)
                elif target_slot == 1:
                    update_match_teams(latest_match.id, latest_match.team1_id, team_id)
                return latest_match.id

        return None

    @staticmethod
    def get_bracket_match_map(matches: List[Match]) -> Dict[str, Match]:
        match_map = {}
        for m in matches:
            if m.bracket_round is not None:
                key = f"{m.bracket_round}_{m.match_number}"
                match_map[key] = m
        return match_map

from typing import List, Dict, Set, Tuple, Optional
from dataclasses import dataclass
import random
from app.models.models import Team, Pairing
from app.database.crud_match import get_all_matchup_pairs


@dataclass
class ScoreGroup:
    score: Tuple[int, int]
    teams: List[Team]


class PairingError(Exception):
    pass


class SwissPairing:
    def __init__(self, tournament_id: int, max_retries: int = 1000):
        self.tournament_id = tournament_id
        self.max_retries = max_retries
        self.used_pairs: Set[Tuple[int, int]] = set()
        self.pairing_history: Set[Tuple[int, int]] = set()

    def _load_matchup_history(self) -> None:
        self.pairing_history = get_all_matchup_pairs(self.tournament_id)

    def _have_played_before(self, team1_id: int, team2_id: int) -> bool:
        return tuple(sorted((team1_id, team2_id))) in self.pairing_history

    def _is_pair_used(self, team1_id: int, team2_id: int) -> bool:
        return tuple(sorted((team1_id, team2_id))) in self.used_pairs

    def _mark_pair_used(self, team1_id: int, team2_id: int) -> None:
        self.used_pairs.add(tuple(sorted((team1_id, team2_id))))

    def _unmark_pair_used(self, team1_id: int, team2_id: int) -> None:
        self.used_pairs.discard(tuple(sorted((team1_id, team2_id))))

    def _group_teams_by_score(self, teams: List[Team]) -> List[ScoreGroup]:
        score_groups: Dict[Tuple[int, int], List[Team]] = {}
        for team in teams:
            key = (team.wins, team.losses)
            if key not in score_groups:
                score_groups[key] = []
            score_groups[key].append(team)

        sorted_scores = sorted(score_groups.keys(), key=lambda x: (-x[0], x[1]))
        return [ScoreGroup(score=s, teams=score_groups[s]) for s in sorted_scores]

    def _select_bye_team(self, teams: List[Team]) -> Optional[Team]:
        eligible = [t for t in teams if t.has_bye == 0]
        if not eligible:
            eligible = teams

        eligible.sort(key=lambda t: (t.wins, -t.seed))
        return eligible[0] if eligible else None

    def _get_valid_opponents(self, team: Team, available_teams: List[Team],
                            allow_cross_score: bool = False) -> List[Team]:
        opponents = []
        for opp in available_teams:
            if opp.id == team.id:
                continue
            if self._is_pair_used(team.id, opp.id):
                continue
            if self._have_played_before(team.id, opp.id):
                continue
            if not allow_cross_score and (team.wins != opp.wins or team.losses != opp.losses):
                continue
            opponents.append(opp)
        return opponents

    def _get_team_score_key(self, team: Team) -> Tuple[int, int]:
        return (team.wins, team.losses)

    def _shuffle_within_score_groups(self, teams: List[Team]) -> List[Team]:
        score_groups: Dict[Tuple[int, int], List[Team]] = {}
        for team in teams:
            key = self._get_team_score_key(team)
            if key not in score_groups:
                score_groups[key] = []
            score_groups[key].append(team)

        result = []
        for score in sorted(score_groups.keys(), key=lambda x: (-x[0], x[1])):
            group_teams = score_groups[score].copy()
            random.shuffle(group_teams)
            result.extend(group_teams)
        return result

    def _try_backtrack_pairing(self, teams: List[Team],
                              current_pairs: List[Pairing],
                              used_ids: Set[int],
                              depth: int = 0) -> Optional[List[Pairing]]:
        if len(used_ids) == len(teams):
            return current_pairs.copy()

        available = [t for t in teams if t.id not in used_ids]
        if not available:
            return current_pairs.copy()

        team = available[0]

        same_score = [t for t in available
                     if t.id != team.id
                     and t.wins == team.wins
                     and t.losses == team.losses]

        cross_score = [t for t in available
                      if t.id != team.id
                      and (t.wins != team.wins or t.losses != team.losses)]

        all_potential = same_score + cross_score

        valid_opponents = []
        for opp in all_potential:
            if self._is_pair_used(team.id, opp.id):
                continue
            if self._have_played_before(team.id, opp.id):
                continue
            valid_opponents.append(opp)

        valid_opponents.sort(key=lambda o: (
            abs(o.wins - team.wins) + abs(o.losses - team.losses),
            abs(o.seed - team.seed)
        ))

        for opponent in valid_opponents:
            self._mark_pair_used(team.id, opponent.id)
            used_ids.add(team.id)
            used_ids.add(opponent.id)

            team1, team2 = team, opponent
            if team1.seed > team2.seed:
                team1, team2 = team2, team1

            current_pairs.append(Pairing(
                team1_id=team1.id,
                team2_id=team2.id,
                is_bye=False
            ))

            result = self._try_backtrack_pairing(teams, current_pairs, used_ids, depth + 1)
            if result is not None:
                return result

            current_pairs.pop()
            used_ids.discard(team.id)
            used_ids.discard(opponent.id)
            self._unmark_pair_used(team.id, opponent.id)

        return None

    def generate_pairings(self, teams: List[Team]) -> List[Pairing]:
        if not teams:
            return []

        self._load_matchup_history()
        self.used_pairs.clear()

        working_teams = teams.copy()
        pairings: List[Pairing] = []

        if len(working_teams) % 2 == 1:
            bye_team = self._select_bye_team(working_teams)
            if bye_team:
                pairings.append(Pairing(
                    team1_id=bye_team.id,
                    team2_id=None,
                    is_bye=True
                ))
                working_teams = [t for t in working_teams if t.id != bye_team.id]

        if not working_teams:
            return pairings

        for retry in range(self.max_retries):
            self.used_pairs.clear()
            shuffled = self._shuffle_within_score_groups(working_teams)
            result = self._try_backtrack_pairing(shuffled, [], set())

            if result is not None:
                pairings.extend(result)
                return self._order_pairings(pairings)

            if retry % 100 == 0:
                random.shuffle(working_teams)

        raise PairingError(
            f"无法在{self.max_retries}次尝试内生成合法配对。"
            f"可能存在无法解决的对阵约束，请检查队伍数量和历史对阵情况。"
        )

    def _order_pairings(self, pairings: List[Pairing]) -> List[Pairing]:
        def get_sort_key(p: Pairing) -> float:
            if p.is_bye:
                return float('inf')
            t1_id = p.team1_id
            t2_id = p.team2_id
            if not t1_id or not t2_id:
                return float('inf')
            return 0

        non_bye = [p for p in pairings if not p.is_bye]
        bye = [p for p in pairings if p.is_bye]

        return non_bye + bye


class DummySwissPairing(SwissPairing):
    def __init__(self, tournament_id: int):
        super().__init__(tournament_id, max_retries=1)
        self._dummy_history: Set[Tuple[int, int]] = set()

    def set_history(self, pairs: List[Tuple[int, int]]) -> None:
        self._dummy_history = set(tuple(sorted(p)) for p in pairs)

    def _load_matchup_history(self) -> None:
        self.pairing_history = self._dummy_history

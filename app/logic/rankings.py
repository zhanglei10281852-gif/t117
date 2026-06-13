from typing import List, Dict, Optional, Set, Tuple
from app.models.models import Team, TeamStanding
from app.database.crud_match import (
    get_opponent_ids, get_head_to_head_winner, get_team_match_scores
)


class RankingCalculator:
    def __init__(self, tournament_id: int):
        self.tournament_id = tournament_id
        self._team_cache: Dict[int, Team] = {}
        self._opponent_cache: Dict[int, List[int]] = {}
        self._standings_cache: Dict[int, TeamStanding] = {}

    def _get_team_win_count(self, team_id: int, teams: List[Team]) -> int:
        for team in teams:
            if team.id == team_id:
                return team.wins
        return 0

    def _get_team_loss_count(self, team_id: int, teams: List[Team]) -> int:
        for team in teams:
            if team.id == team_id:
                return team.losses
        return 0

    def _get_team_match_count(self, team_id: int, teams: List[Team]) -> int:
        return self._get_team_win_count(team_id, teams) + self._get_team_loss_count(team_id, teams)

    def calculate_buchholz(self, team: Team, all_teams: List[Team]) -> float:
        opponent_ids = get_opponent_ids(self.tournament_id, team.id)
        if not opponent_ids:
            return 0.0

        buchholz_sum = 0.0
        for opp_id in opponent_ids:
            opp_wins = self._get_team_win_count(opp_id, all_teams)
            buchholz_sum += opp_wins
        return buchholz_sum

    def calculate_median_buchholz(self, team: Team, all_teams: List[Team]) -> float:
        opponent_ids = get_opponent_ids(self.tournament_id, team.id)
        if not opponent_ids:
            return 0.0

        opponent_wins = []
        for opp_id in opponent_ids:
            opponent_wins.append(self._get_team_win_count(opp_id, all_teams))

        if len(opponent_wins) <= 2:
            return sum(opponent_wins)

        sorted_wins = sorted(opponent_wins)
        trimmed = sorted_wins[1:-1]
        return sum(trimmed)

    def calculate_opponent_win_rate(self, team: Team, all_teams: List[Team]) -> float:
        opponent_ids = get_opponent_ids(self.tournament_id, team.id)
        if not opponent_ids:
            return 0.0

        total_win_rate = 0.0
        valid_opponents = 0
        for opp_id in opponent_ids:
            opp_wins = self._get_team_win_count(opp_id, all_teams)
            opp_matches = self._get_team_match_count(opp_id, all_teams)
            if opp_matches > 0:
                total_win_rate += opp_wins / opp_matches
                valid_opponents += 1

        if valid_opponents == 0:
            return 0.0
        return total_win_rate / valid_opponents

    def calculate_head_to_head(self, team: Team, tied_teams: List[Team]) -> int:
        if len(tied_teams) < 2:
            return 0

        wins = 0
        for other in tied_teams:
            if other.id == team.id:
                continue
            winner = get_head_to_head_winner(self.tournament_id, team.id, other.id)
            if winner == team.id:
                wins += 1
        return wins

    def _get_head_to_head_comparison(self, team1_id: int, team2_id: int) -> Optional[int]:
        return get_head_to_head_winner(self.tournament_id, team1_id, team2_id)

    def _compare_teams(self, standing1: TeamStanding, standing2: TeamStanding,
                       all_standings: List[TeamStanding]) -> int:
        team1 = standing1.team
        team2 = standing2.team

        if team1.wins != team2.wins:
            return -1 if team1.wins > team2.wins else 1

        if standing1.median_buchholz != standing2.median_buchholz:
            return -1 if standing1.median_buchholz > standing2.median_buchholz else 1

        if standing1.buchholz != standing2.buchholz:
            return -1 if standing1.buchholz > standing2.buchholz else 1

        tied_standings = [s for s in all_standings
                         if s.team.wins == team1.wins
                         and s.median_buchholz == standing1.median_buchholz
                         and s.buchholz == standing1.buchholz]

        if len(tied_standings) >= 2:
            tied_teams = [s.team for s in tied_standings]
            h2h_1 = self.calculate_head_to_head(team1, tied_teams)
            h2h_2 = self.calculate_head_to_head(team2, tied_teams)
            if h2h_1 != h2h_2:
                return -1 if h2h_1 > h2h_2 else 1

            if len(tied_standings) == 2:
                h2h_winner = self._get_head_to_head_comparison(team1.id, team2.id)
                if h2h_winner == team1.id:
                    return -1
                elif h2h_winner == team2.id:
                    return 1

        if standing1.opponent_win_rate != standing2.opponent_win_rate:
            return -1 if standing1.opponent_win_rate > standing2.opponent_win_rate else 1

        if standing1.scores_for != standing2.scores_for:
            return -1 if standing1.scores_for > standing2.scores_for else 1

        score_diff1 = standing1.scores_for - standing1.scores_against
        score_diff2 = standing2.scores_for - standing2.scores_against
        if score_diff1 != score_diff2:
            return -1 if score_diff1 > score_diff2 else 1

        if team1.seed != team2.seed:
            return -1 if team1.seed < team2.seed else 1

        return 0

    def calculate_standings(self, teams: List[Team]) -> List[TeamStanding]:
        standings: List[TeamStanding] = []

        for team in teams:
            opponents = get_opponent_ids(self.tournament_id, team.id)
            scores_for, scores_against = get_team_match_scores(self.tournament_id, team.id)

            standing = TeamStanding(
                team=team,
                buchholz=self.calculate_buchholz(team, teams),
                median_buchholz=self.calculate_median_buchholz(team, teams),
                opponent_win_rate=self.calculate_opponent_win_rate(team, teams),
                opponents=opponents,
                scores_for=scores_for,
                scores_against=scores_against
            )
            standings.append(standing)

        for i in range(len(standings)):
            tied_standings = [s for s in standings
                             if s.team.wins == standings[i].team.wins
                             and s.median_buchholz == standings[i].median_buchholz
                             and s.buchholz == standings[i].buchholz]
            tied_teams = [s.team for s in tied_standings]
            standings[i].head_to_head_wins = self.calculate_head_to_head(
                standings[i].team, tied_teams
            )

        from functools import cmp_to_key
        standings.sort(key=cmp_to_key(lambda a, b: self._compare_teams(a, b, standings)))

        current_rank = 1
        for i, standing in enumerate(standings):
            if i > 0:
                prev = standings[i-1]
                if (standing.team.wins != prev.team.wins
                    or standing.median_buchholz != prev.median_buchholz
                    or standing.buchholz != prev.buchholz
                    or standing.head_to_head_wins != prev.head_to_head_wins):
                    current_rank = i + 1
            standing.rank = current_rank

        return standings

    def get_teams_for_playoff(self, standings: List[TeamStanding],
                              count: int, active_only: bool = True) -> List[Team]:
        if active_only:
            eligible = [s for s in standings if s.team.status == "active"]
        else:
            eligible = standings

        sorted_standings = sorted(eligible, key=lambda s: (
            s.rank,
            -s.team.wins,
            -s.median_buchholz,
            -s.buchholz,
            s.team.seed
        ))

        return [s.team for s in sorted_standings[:count]]

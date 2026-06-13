from typing import List, Optional, Dict, Tuple
from app.models.models import (
    Tournament, Team, Match, Round, TeamStanding, Pairing,
    TournamentPhase, TeamStatus, MatchStatus, RoundStatus
)
from app.database import crud_tournament, crud_team, crud_round, crud_match
from app.logic.swiss_pairing import SwissPairing, PairingError
from app.logic.rankings import RankingCalculator
from app.logic.double_elimination import (
    DoubleEliminationBracket, BracketProgression, BracketMatchInfo
)


class TournamentError(Exception):
    pass


class ScoreValidationError(TournamentError):
    pass


class PhaseTransitionError(TournamentError):
    pass


class TournamentManager:
    def __init__(self, tournament_id: Optional[int] = None):
        self.tournament_id = tournament_id
        self._tournament: Optional[Tournament] = None
        self._bracket: Optional[DoubleEliminationBracket] = None
        self._bracket_structure: List[BracketMatchInfo] = []
        self._playoff_team_count: int = 8
        self._load_tournament()

    def _load_tournament(self) -> None:
        if self.tournament_id:
            self._tournament = crud_tournament.get_tournament(self.tournament_id)

    def create_tournament(self, name: str, swiss_format: str = "bo1",
                        playoff_format: str = "bo3",
                        advance_wins: int = 3, eliminate_losses: int = 3,
                        playoff_teams: int = 8) -> int:
        if advance_wins <= 0 or eliminate_losses <= 0:
            raise TournamentError("晋级胜场和淘汰败场必须大于0")
        if playoff_teams < 2:
            raise TournamentError("淘汰赛队伍数至少为2")

        self.tournament_id = crud_tournament.create_tournament(
            name, swiss_format, playoff_format, advance_wins, eliminate_losses)
        self._playoff_team_count = playoff_teams
        self._load_tournament()
        return self.tournament_id

    def load_tournament(self, tournament_id: int) -> None:
        self.tournament_id = tournament_id
        self._load_tournament()
        if not self._tournament:
            raise TournamentError(f"找不到赛事 ID {tournament_id}")

    def get_tournament(self) -> Optional[Tournament]:
        return self._tournament

    def add_team(self, name: str, seed: Optional[int] = None) -> int:
        if self.tournament_id is None:
            raise TournamentError("请先创建或加载赛事")
        if self._tournament and self._tournament.phase != TournamentPhase.SETUP:
            raise TournamentError("赛事已开始，无法添加队伍")
        if not name.strip():
            raise TournamentError("队伍名称不能为空")

        existing_teams = crud_team.get_teams_by_tournament(self.tournament_id)
        if seed is None:
            seed = len(existing_teams) + 1
        else:
            for t in existing_teams:
                if t.seed == seed:
                    raise TournamentError(f"种子排名 {seed} 已存在")

        return crud_team.add_team(self.tournament_id, name.strip(), seed)

    def update_team(self, team_id: int, name: str, seed: int) -> None:
        if self._tournament and self._tournament.phase != TournamentPhase.SETUP:
            raise TournamentError("赛事已开始，无法修改队伍")
        team = crud_team.get_team(team_id)
        if not team:
            team.name = name.strip()
            team.seed = seed
            crud_team.update_team(team)

    def delete_team(self, team_id: int) -> None:
        if self._tournament and self._tournament.phase != TournamentPhase.SETUP:
            raise TournamentError("赛事已开始，无法删除队伍")
        crud_team.delete_team(team_id)

    def get_teams(self, status: Optional[TeamStatus] = None) -> List[Team]:
        if not self.tournament_id:
            return []
        return crud_team.get_teams_by_tournament(self.tournament_id, status)

    def get_active_teams(self) -> List[Team]:
        return self.get_teams(TeamStatus.ACTIVE)

    def validate_and_set_playoff_count(self, count: int) -> None:
        if count < 2:
            raise TournamentError("淘汰赛队伍数至少为2")
        if count % 2 != 0:
            raise TournamentError("淘汰赛队伍数必须为偶数")
        self._playoff_team_count = count

    def start_swiss(self) -> None:
        if self._tournament is None:
            raise TournamentError("请先创建赛事")

        teams = self.get_teams()
        if len(teams) < 2:
            raise PhaseTransitionError("至少需要2支队伍才能开始比赛")

        if self._playoff_team_count > len(teams):
            raise PhaseTransitionError(
                f"淘汰赛队伍数({self._playoff_team_count})不能大于参赛队伍数({len(teams)})")

        self._tournament.phase = TournamentPhase.SWISS
        self._tournament.current_round = 0
        crud_tournament.update_tournament(self._tournament)

    def generate_next_swiss_round(self) -> Round:
        if self._tournament is None:
            raise TournamentError("请先创建赛事")
        if self._tournament.phase != TournamentPhase.SWISS:
            raise PhaseTransitionError("当前不是瑞士轮阶段")

        if self._tournament.current_round > 0:
            prev_round = crud_round.get_round_by_number(
                self.tournament_id, self._tournament.current_round, "swiss")
            if prev_round and not crud_match.check_round_complete(prev_round.id):
                raise PhaseTransitionError("上一轮比赛尚未全部完成，无法开启下一轮")

        active_teams = self.get_active_teams()
        if len(active_teams) <= self._playoff_team_count:
            raise PhaseTransitionError(
                f"剩余活跃队伍({len(active_teams)})已达到淘汰赛名额({self._playoff_team_count})，"
                f"请进入淘汰赛阶段")

        advanced_count = len([t for t in self.get_teams()
                       if t.status == TeamStatus.ADVANCED])
        eliminated_count = len([t for t in self.get_teams()
                               if t.status == TeamStatus.ELIMINATED])

        if advanced_count >= self._playoff_team_count:
            raise PhaseTransitionError(
                f"已有足够队伍晋级({advanced_count})，请进入淘汰赛阶段")

        if len(active_teams) == 0:
            raise PhaseTransitionError("没有活跃队伍可以配对")

        next_round_num = self._tournament.current_round + 1

        existing_round = crud_round.get_round_by_number(
            self.tournament_id, next_round_num, "swiss")
        if existing_round:
            crud_match.delete_matches_by_round(existing_round.id)
            crud_round.update_round_status(existing_round.id, RoundStatus.PENDING)
            round_id = existing_round.id
        else:
            round_id = crud_round.create_round(
                self.tournament_id, next_round_num, "swiss",
                self._tournament.swiss_format)

        pairer = SwissPairing(self.tournament_id)
        try:
            pairings = pairer.generate_pairings(active_teams)
        except PairingError as e:
            raise TournamentError(str(e))

        match_num = 1
        for pairing in pairings:
            if pairing.is_bye:
                crud_match.create_match(
                    self.tournament_id, round_id, match_num,
                    pairing.team1_id, None, is_bye=True)
                if pairing.team1_id:
                    self._handle_bye_win(pairing.team1_id, next_round_num)
            else:
                crud_match.create_match(
                    self.tournament_id, round_id, match_num,
                    pairing.team1_id, pairing.team2_id)
            match_num += 1

        crud_round.update_round_status(round_id, RoundStatus.IN_PROGRESS)
        self._tournament.current_round = next_round_num
        crud_tournament.update_tournament(self._tournament)

        round_obj = crud_round.get_round(round_id)
        return round_obj

    def _handle_bye_win(self, team_id: int, round_num: int) -> None:
        team = crud_team.get_team(team_id)
        if not team:
            new_wins = team.wins + 1
            new_status = team.status
            eliminated_at = team.eliminated_at_round

            if new_wins >= self._tournament.advance_wins:
                new_status = TeamStatus.ADVANCED
            elif team.losses >= self._tournament.eliminate_losses:
                    pass

            crud_team.update_team_record(
                team_id, new_wins, team.losses, new_status, eliminated_at)

    def _get_wins_needed(self, match_format: str) -> int:
        if match_format == "bo1":
            return 1
        elif match_format == "bo3":
            return 2
        elif match_format == "bo5":
            return 3
        else:
            return 1

    def validate_score(self, score1: int, score2: int, match_format: str) -> None:
        wins_needed = self._get_wins_needed(match_format)

        if score1 < 0 or score2 < 0:
            raise ScoreValidationError("比分不能为负数")

        if score1 == score2:
            raise ScoreValidationError("比分不能平局")

        max_score = max(score1, score2)
        min_score = min(score1, score2)

        if max_score != wins_needed:
            raise ScoreValidationError(
                f"{match_format.upper()} 赛制需要赢 {wins_needed} 场才能获胜，"
                f"当前比分 {score1}-{score2} 无效")

        if min_score >= wins_needed:
            raise ScoreValidationError(
                f"比分无效，双方不能同时达到获胜场数")

    def record_match_result(self, match_id: int, score1: int, score2: int) -> Match:
        match = crud_match.get_match(match_id)
        if not match:
            raise TournamentError("找不到比赛")

        if match.status == MatchStatus.COMPLETED:
            raise TournamentError("该比赛已经录入过结果了")

        round_obj = crud_round.get_round(match.round_id)
        if not round_obj:
            raise TournamentError("找不到比赛所属轮次")

        self.validate_score(score1, score2, round_obj.format)

        winner_id = match.team1_id if score1 > score2 else match.team2_id
        loser_id = match.team2_id if score1 > score2 else match.team1_id

        crud_match.update_match_result(match_id, score1, score2, winner_id)

        if round_obj.phase == "swiss":
            self._update_team_records_swiss(
                winner_id, loser_id, round_obj.round_number)
        elif round_obj.phase == "playoff":
            self._update_team_records_playoff(
                winner_id, loser_id)
            self._advance_bracket_teams(match, winner_id, loser_id)

        return crud_match.get_match(match_id)

    def _update_team_records_swiss(self, winner_id: int, loser_id: int,
                                  round_num: int) -> None:
        winner = crud_team.get_team(winner_id)
        loser = crud_team.get_team(loser_id)

        if winner:
            new_wins = winner.wins + 1
            new_status = winner.status
            eliminated_at = winner.eliminated_at_round

            if new_wins >= self._tournament.advance_wins:
                new_status = TeamStatus.ADVANCED

            crud_team.update_team_record(
                winner_id, new_wins, winner.losses, new_status, eliminated_at)

        if loser:
            new_losses = loser.losses + 1
            new_status = loser.status
            eliminated_at = loser.eliminated_at_round

            if new_losses >= self._tournament.eliminate_losses:
                new_status = TeamStatus.ELIMINATED
                eliminated_at = round_num

            crud_team.update_team_record(
                loser_id, loser.wins, new_losses, new_status, eliminated_at)

    def _update_team_records_playoff(self, winner_id: int, loser_id: int) -> None:
        winner = crud_team.get_team(winner_id)
        loser = crud_team.get_team(loser_id)

        if winner:
            crud_team.update_team_record(
                winner_id, winner.wins + 1, winner.losses,
                winner.status, winner.eliminated_at_round)

        if loser:
            crud_team.update_team_record(
                loser_id, loser.wins, loser.losses + 1,
                TeamStatus.ELIMINATED if loser.status == TeamStatus.ACTIVE else loser.status,
                loser.eliminated_at_round)

    def _advance_bracket_teams(self, match: Match, winner_id: int, loser_id: int) -> None:
        if not self._bracket:
            return

        all_matches = crud_match.get_matches_by_tournament(self.tournament_id)
        match_map = BracketProgression.get_bracket_match_map(all_matches)

        BracketProgression.advance_winner(
            match, match_map, self._bracket_structure, winner_id, is_winner=True)

        lower_final_rounds = ["lower_final", "grand_final", "grand_final_reset"]
        if match.bracket_round not in lower_final_rounds:
            pass
        else:
            BracketProgression.advance_winner(
                match, match_map, self._bracket_structure, loser_id, is_winner=False)

    def get_current_swiss_round(self) -> Optional[Round]:
        if not self._tournament or self._tournament.current_round == 0:
            return None
        return crud_round.get_round_by_number(
            self.tournament_id, self._tournament.current_round, "swiss")

    def get_round_matches(self, round_id: int) -> List[Match]:
        return crud_match.get_matches_by_round(round_id)

    def calculate_standings(self) -> List[TeamStanding]:
        teams = self.get_teams()
        if not teams:
            return []
        calculator = RankingCalculator(self.tournament_id)
        return calculator.calculate_standings(teams)

    def check_swiss_complete(self) -> bool:
        if not self._tournament:
            return False

        advanced = [t for t in self.get_teams()
                    if t.status == TeamStatus.ADVANCED]
        return len(advanced) >= self._playoff_team_count

    def start_playoff(self) -> None:
        if self._tournament is None:
            raise TournamentError("请先创建赛事")

        if self._tournament.phase == TournamentPhase.PLAYOFF:
            return

        if self._tournament.phase not in [TournamentPhase.SWISS, TournamentPhase.SETUP]:
            raise PhaseTransitionError("当前阶段无法进入淘汰赛")

        standings = self.calculate_standings()
        calculator = RankingCalculator(self.tournament_id)
        playoff_teams = calculator.get_teams_for_playoff(
            standings, self._playoff_team_count, active_only=False)

        if len(playoff_teams) < 2:
            raise PhaseTransitionError("淘汰赛至少需要2支队伍")

        for team in playoff_teams:
            if team.status != TeamStatus.ADVANCED:
                team.status = TeamStatus.ADVANCED
                crud_team.update_team(team)

        self._bracket = DoubleEliminationBracket(len(playoff_teams))
        self._bracket_structure = self._bracket.generate_bracket_structure()

        seed_to_team = {i + 1: team for i, team in enumerate(playoff_teams)}

        all_rounds = self._bracket.get_all_round_names()
        for round_name in all_rounds:
            match_infos = self._bracket.get_match_infos_by_round(round_name)
            if not match_infos:
                continue

            round_num = all_rounds.index(round_name) + 1
            round_id = crud_round.create_round(
                self.tournament_id, round_num, "playoff",
                self._tournament.playoff_format)

            for info in match_infos:
                team1_id = None
                team2_id = None

                if info.team1_seed:
                    team1_id = seed_to_team.get(info.team1_seed).id if info.team1_seed in seed_to_team else None
                if info.team2_seed:
                    team2_id = seed_to_team.get(info.team2_seed).id if info.team2_seed in seed_to_team else None

                match_id = crud_match.create_match(
                    self.tournament_id, round_id, info.position,
                    team1_id, team2_id,
                    is_bye=(team1_id is not None and team2_id is None),
                    bracket_side=info.bracket_side,
                    bracket_round=info.bracket_round)

                if team1_id and team2_id is None:
                    crud_match.update_match_result(
                        match_id, 1, 0, team1_id)
                    self._auto_advance_bye(match_id, team1_id)

        self._tournament.phase = TournamentPhase.PLAYOFF
        self._tournament.current_round = 1
        crud_tournament.update_tournament(self._tournament)

    def _auto_advance_bye(self, match_id: int, winner_id: int) -> None:
        match = crud_match.get_match(match_id)
        if not match or not self._bracket:
            return

        all_matches = crud_match.get_matches_by_tournament(self.tournament_id)
        match_map = BracketProgression.get_bracket_match_map(all_matches)

        BracketProgression.advance_winner(
            match, match_map, self._bracket_structure, winner_id, is_winner=True)

    def get_bracket(self) -> Optional[DoubleEliminationBracket]:
        return self._bracket

    def get_bracket_structure(self) -> List[BracketMatchInfo]:
        return self._bracket_structure

    def get_playoff_matches_by_round(self, round_name: str) -> List[Match]:
        return crud_match.get_matches_by_bracket(self.tournament_id, round_name)

    def get_playoff_round_names(self) -> List[str]:
        if self._bracket:
            return self._bracket.get_all_round_names()
        return []

    def get_round_display_name(self, round_name: str) -> str:
        if self._bracket:
            return self._bracket.get_round_display_name(round_name)
        return round_name

    def check_playoff_complete(self) -> bool:
        if not self._tournament or self._tournament.phase != TournamentPhase.PLAYOFF:
            return False

        all_matches = crud_match.get_matches_by_tournament(self.tournament_id)
        pending = [m for m in all_matches if m.status == MatchStatus.PENDING and not m.is_bye]
        return len(pending) == 0

    def complete_tournament(self) -> None:
        if not self._tournament:
            raise TournamentError("请先创建赛事")
        if not self.check_playoff_complete():
            raise PhaseTransitionError("淘汰赛尚未完成")

        self._tournament.phase = TournamentPhase.COMPLETED
        crud_tournament.update_tournament(self._tournament)

    def get_team_name(self, team_id: Optional[int]) -> str:
        if not team_id:
            return "轮空"
        team = crud_team.get_team(team_id)
        return team.name if team else "未知"

    def get_playoff_team_count(self) -> int:
        return self._playoff_team_count

    def get_all_rounds(self) -> List[Round]:
        if not self.tournament_id:
            return []
        return crud_round.get_rounds_by_tournament(self.tournament_id)

    def get_swiss_rounds(self) -> List[Round]:
        if not self.tournament_id:
            return []
        return crud_round.get_rounds_by_phase(self.tournament_id, "swiss")

    def get_playoff_rounds(self) -> List[Round]:
        if not self.tournament_id:
            return []
        return crud_round.get_rounds_by_phase(self.tournament_id, "playoff")

    def get_winner(self) -> Optional[Team]:
        if not self._tournament or self._tournament.phase != TournamentPhase.COMPLETED:
            return None

        all_matches = crud_match.get_matches_by_tournament(self.tournament_id)
        final_matches = [m for m in all_matches
                       if m.bracket_round in ["grand_final", "grand_final_reset"]
                       and m.status == MatchStatus.COMPLETED]

        if not final_matches:
            return None

        final_matches.sort(key=lambda m: m.id)
        last_final = final_matches[-1]
        if last_final.winner_id:
            return crud_team.get_team(last_final.winner_id)
        return None

    def export_data(self) -> Dict:
        if not self.tournament_id:
            return {}

        tournament = self._tournament
        teams = self.get_teams()
        rounds = self.get_all_rounds()
        matches = crud_match.get_matches_by_tournament(self.tournament_id)
        standings = self.calculate_standings()

        team_dict = {t.id: t for t in teams}
        round_dict = {r.id: r for r in rounds}

        data = {
            "tournament": {
                "id": tournament.id,
                "name": tournament.name,
                "phase": tournament.phase.value,
                "swiss_format": tournament.swiss_format,
                "playoff_format": tournament.playoff_format,
                "advance_wins": tournament.advance_wins,
                "eliminate_losses": tournament.eliminate_losses,
                "playoff_team_count": self._playoff_team_count
            },
            "teams": [
                {
                    "id": t.id,
                    "name": t.name,
                    "seed": t.seed,
                    "wins": t.wins,
                    "losses": t.losses,
                    "status": t.status.value,
                    "has_bye": t.has_bye,
                    "eliminated_at_round": t.eliminated_at_round
                } for t in teams
            ],
            "standings": [
                {
                    "rank": s.rank,
                    "team_id": s.team.id,
                    "team_name": s.team.name,
                    "wins": s.team.wins,
                    "losses": s.team.losses,
                    "buchholz": s.buchholz,
                    "median_buchholz": s.median_buchholz,
                    "head_to_head_wins": s.head_to_head_wins,
                    "opponent_win_rate": s.opponent_win_rate,
                    "scores_for": s.scores_for,
                    "scores_against": s.scores_against
                } for s in standings
            ],
            "rounds": [
                {
                    "id": r.id,
                    "round_number": r.round_number,
                    "phase": r.phase,
                    "format": r.format,
                    "status": r.status.value
                } for r in rounds
            ],
            "matches": [
                {
                    "id": m.id,
                    "round_id": m.round_id,
                    "round_number": round_dict[m.round_id].round_number if m.round_id in round_dict else 0,
                    "phase": round_dict[m.round_id].phase if m.round_id in round_dict else "",
                    "match_number": m.match_number,
                    "team1_id": m.team1_id,
                    "team1_name": team_dict[m.team1_id].name if m.team1_id in team_dict else None,
                    "team2_id": m.team2_id,
                    "team2_name": team_dict[m.team2_id].name if m.team2_id in team_dict else None,
                    "team1_score": m.team1_score,
                    "team2_score": m.team2_score,
                    "winner_id": m.winner_id,
                    "winner_name": team_dict[m.winner_id].name if m.winner_id in team_dict else None,
                    "status": m.status.value,
                    "is_bye": m.is_bye,
                    "bracket_side": m.bracket_side,
                    "bracket_round": m.bracket_round
                } for m in matches
            ]
        }

        winner = self.get_winner()
        if winner:
            data["tournament"]["winner"] = {
                "id": winner.id,
                "name": winner.name
            }

        return data

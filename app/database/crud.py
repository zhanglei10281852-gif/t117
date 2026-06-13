from typing import List, Optional, Dict, Any
from app.database.connection import get_connection
from app.models.models import (
    Tournament, Team, Match, Round,
    TournamentPhase, TeamStatus, MatchStatus, RoundStatus
)


def create_tournament(name: str, swiss_format: str = "bo1",
                      playoff_format: str = "bo3",
                      advance_wins: int = 3, eliminate_losses: int = 3) -> int:
    conn = get_connection()
    cursor = conn.cursor()
    cursor.execute("""
    INSERT INTO tournament (name, phase, current_round, swiss_format, playoff_format, advance_wins, eliminate_losses)
    VALUES (?, ?, ?, ?, ?, ?, ?)
    """, (name, TournamentPhase.SETUP.value, 0, swiss_format, playoff_format, advance_wins, eliminate_losses))
    tournament_id = cursor.lastrowid
    conn.commit()
    conn.close()
    return tournament_id


def get_tournament(tournament_id: int) -> Optional[Tournament]:
    conn = get_connection()
    cursor = conn.cursor()
    cursor.execute("SELECT * FROM tournament WHERE id = ?", (tournament_id,))
    row = cursor.fetchone()
    conn.close()
    if row:
        return Tournament(
            id=row["id"],
            name=row["name"],
            phase=TournamentPhase(row["phase"]),
            current_round=row["current_round"],
            swiss_format=row["swiss_format"],
            playoff_format=row["playoff_format"],
            advance_wins=row["advance_wins"],
            eliminate_losses=row["eliminate_losses"]
        )
    return None


def get_all_tournaments() -> List[Tournament]:
    conn = get_connection()
    cursor = conn.cursor()
    cursor.execute("SELECT * FROM tournament ORDER BY created_at DESC")
    rows = cursor.fetchall()
    conn.close()
    return [Tournament(
        id=row["id"],
        name=row["name"],
        phase=TournamentPhase(row["phase"]),
        current_round=row["current_round"],
        swiss_format=row["swiss_format"],
        playoff_format=row["playoff_format"],
        advance_wins=row["advance_wins"],
        eliminate_losses=row["eliminate_losses"]
    ) for row in rows]


def update_tournament(tournament: Tournament) -> None:
    conn = get_connection()
    cursor = conn.cursor()
    cursor.execute("""
    UPDATE tournament SET name=?, phase=?, current_round=?, swiss_format=?, playoff_format=?, advance_wins=?, eliminate_losses=?
    WHERE id=?
    """, (tournament.name, tournament.phase.value, tournament.current_round,
          tournament.swiss_format, tournament.playoff_format,
          tournament.advance_wins, tournament.eliminate_losses, tournament.id))
    conn.commit()
    conn.close()


def update_tournament_phase(tournament_id: int, phase: TournamentPhase) -> None:
    conn = get_connection()
    cursor = conn.cursor()
    cursor.execute("UPDATE tournament SET phase=? WHERE id=?",
                   (phase.value, tournament_id))
    conn.commit()
    conn.close()


def update_tournament_current_round(tournament_id: int, round_num: int) -> None:
    conn = get_connection()
    cursor = conn.cursor()
    cursor.execute("UPDATE tournament SET current_round=? WHERE id=?",
                   (round_num, tournament_id))
    conn.commit()
    conn.close()


def delete_tournament(tournament_id: int) -> None:
    conn = get_connection()
    cursor = conn.cursor()
    cursor.execute("DELETE FROM tournament WHERE id=?", (tournament_id,))
    conn.commit()
    conn.close()


def add_team(tournament_id: int, name: str, seed: int) -> int:
    conn = get_connection()
    cursor = conn.cursor()
    cursor.execute("""
    INSERT INTO team (tournament_id, name, seed, wins, losses, status, has_bye)
    VALUES (?, ?, ?, 0, 0, ?, 0)
    """, (tournament_id, name, seed, TeamStatus.ACTIVE.value))
    team_id = cursor.lastrowid
    conn.commit()
    conn.close()
    return team_id


def get_team(team_id: int) -> Optional[Team]:
    conn = get_connection()
    cursor = conn.cursor()
    cursor.execute("SELECT * FROM team WHERE id=?", (team_id,))
    row = cursor.fetchone()
    conn.close()
    if row:
        return Team(
            id=row["id"],
            tournament_id=row["tournament_id"],
            name=row["name"],
            seed=row["seed"],
            wins=row["wins"],
            losses=row["losses"],
            status=TeamStatus(row["status"]),
            has_bye=row["has_bye"],
            eliminated_at_round=row["eliminated_at_round"]
        )
    return None


def get_teams_by_tournament(tournament_id: int, status: Optional[TeamStatus] = None) -> List[Team]:
    conn = get_connection()
    cursor = conn.cursor()
    if status:
        cursor.execute("SELECT * FROM team WHERE tournament_id=? AND status=? ORDER BY seed",
                       (tournament_id, status.value))
    else:
        cursor.execute("SELECT * FROM team WHERE tournament_id=? ORDER BY seed",
                       (tournament_id,))
    rows = cursor.fetchall()
    conn.close()
    return [Team(
        id=row["id"],
        tournament_id=row["tournament_id"],
        name=row["name"],
        seed=row["seed"],
        wins=row["wins"],
        losses=row["losses"],
        status=TeamStatus(row["status"]),
        has_bye=row["has_bye"],
        eliminated_at_round=row["eliminated_at_round"]
    ) for row in rows]


def get_active_teams(tournament_id: int) -> List[Team]:
    return get_teams_by_tournament(tournament_id, TeamStatus.ACTIVE)


def update_team(team: Team) -> None:
    conn = get_connection()
    cursor = conn.cursor()
    cursor.execute("""
    UPDATE team SET name=?, seed=?, wins=?, losses=?, status=?, has_bye=?, eliminated_at_round=?
    WHERE id=?
    """, (team.name, team.seed, team.wins, team.losses, team.status.value,
          team.has_bye, team.eliminated_at_round, team.id))
    conn.commit()
    conn.close()


def update_team_record(team_id: int, wins: int, losses: int,
                       status: TeamStatus, eliminated_at_round: Optional[int] = None) -> None:
    conn = get_connection()
    cursor = conn.cursor()
    cursor.execute("""
    UPDATE team SET wins=?, losses=?, status=?, eliminated_at_round=? WHERE id=?
    """, (wins, losses, status.value, eliminated_at_round, team_id))
    conn.commit()
    conn.close()


def update_team_bye(team_id: int, has_bye: int = 1) -> None:
    conn = get_connection()
    cursor = conn.cursor()
    cursor.execute("UPDATE team SET has_bye=? WHERE id=?", (has_bye, team_id))
    conn.commit()
    conn.close()


def delete_team(team_id: int) -> None:
    conn = get_connection()
    cursor = conn.cursor()
    cursor.execute("DELETE FROM team WHERE id=?", (team_id,))
    conn.commit()
    conn.close()


def create_round(tournament_id: int, round_number: int,
                 phase: str, fmt: str) -> int:
    conn = get_connection()
    cursor = conn.cursor()
    cursor.execute("""
    INSERT INTO round (tournament_id, round_number, phase, format, status)
    VALUES (?, ?, ?, ?, ?)
    """, (tournament_id, round_number, phase, fmt, RoundStatus.PENDING.value))
    round_id = cursor.lastrowid
    conn.commit()
    conn.close()
    return round_id


def get_round(round_id: int) -> Optional[Round]:
    conn = get_connection()
    cursor = conn.cursor()
    cursor.execute("SELECT * FROM round WHERE id=?", (round_id,))
    row = cursor.fetchone()
    conn.close()
    if row:
        return Round(
            id=row["id"],
            tournament_id=row["tournament_id"],
            round_number=row["round_number"],
            phase=row["phase"],
            format=row["format"],
            status=RoundStatus(row["status"])
        )
    return None


def get_round_by_number(tournament_id: int, round_number: int, phase: str) -> Optional[Round]:
    conn = get_connection()
    cursor = conn.cursor()
    cursor.execute("SELECT * FROM round WHERE tournament_id=? AND round_number=? AND phase=?",
                   (tournament_id, round_number, phase))
    row = cursor.fetchone()
    conn.close()
    if row:
        return Round(
            id=row["id"],
            tournament_id=row["tournament_id"],
            round_number=row["round_number"],
            phase=row["phase"],
            format=row["format"],
            status=RoundStatus(row["status"])
        )
    return None


def get_rounds_by_tournament(tournament_id: int) -> List[Round]:
    conn = get_connection()
    cursor = conn.cursor()
    cursor.execute("SELECT * FROM round WHERE tournament_id=? ORDER BY phase, round_number",
                   (tournament_id,))
    rows = cursor.fetchall()
    conn.close()
    return [Round(
        id=row["id"],
        tournament_id=row["tournament_id"],
        round_number=row["round_number"],
        phase=row["phase"],
        format=row["format"],
        status=RoundStatus(row["status"])
    ) for row in rows]


def get_rounds_by_phase(tournament_id: int, phase: str) -> List[Round]:
    conn = get_connection()
    cursor = conn.cursor()
    cursor.execute("SELECT * FROM round WHERE tournament_id=? AND phase=? ORDER BY round_number",
                   (tournament_id, phase))
    rows = cursor.fetchall()
    conn.close()
    return [Round(
        id=row["id"],
        tournament_id=row["tournament_id"],
        round_number=row["round_number"],
        phase=row["phase"],
        format=row["format"],
        status=RoundStatus(row["status"])
    ) for row in rows]


def update_round_status(round_id: int, status: RoundStatus) -> None:
    conn = get_connection()
    cursor = conn.cursor()
    cursor.execute("UPDATE round SET status=? WHERE id=?",
                   (status.value, round_id))
    conn.commit()
    conn.close()


def create_match(tournament_id: int, round_id: int, match_number: int,
                 team1_id: Optional[int], team2_id: Optional[int],
                 is_bye: bool = False, bracket_side: Optional[str] = None,
                 bracket_round: Optional[str] = None) -> int:
    conn = get_connection()
    cursor = conn.cursor()
    cursor.execute("""
    INSERT INTO match (tournament_id, round_id, match_number, team1_id, team2_id,
                       team1_score, team2_score, winner_id, status, is_bye, bracket_side, bracket_round)
    VALUES (?, ?, ?, ?, ?, 0, 0, NULL, ?, ?, ?, ?)
    """, (tournament_id, round_id, match_number, team1_id, team2_id,
          MatchStatus.PENDING.value, 1 if is_bye else 0, bracket_side, bracket_round))
    match_id = cursor.lastrowid

    if not is_bye and team1_id and team2_id:
        round_obj = get_round(round_id)
        cursor.execute("""
        INSERT INTO matchup_history (tournament_id, team1_id, team2_id, match_id, round_number)
        VALUES (?, ?, ?, ?, ?)
        """, (tournament_id, team1_id, team2_id, match_id, round_obj.round_number if round_obj else 0))

    conn.commit()
    conn.close()
    return match_id


def get_match(match_id: int) -> Optional[Match]:
    conn = get_connection()
    cursor = conn.cursor()
    cursor.execute("SELECT * FROM match WHERE id=?", (match_id,))
    row = cursor.fetchone()
    conn.close()
    if row:
        return Match(
            id=row["id"],
            tournament_id=row["tournament_id"],
            round_id=row["round_id"],
            match_number=row["match_number"],
            team1_id=row["team1_id"],
            team2_id=row["team2_id"],
            team1_score=row["team1_score"],
            team2_score=row["team2_score"],
            winner_id=row["winner_id"],
            status=MatchStatus(row["status"]),
            is_bye=bool(row["is_bye"]),
            bracket_side=row["bracket_side"],
            bracket_round=row["bracket_round"]
        )
    return None


def get_matches_by_round(round_id: int) -> List[Match]:
    conn = get_connection()
    cursor = conn.cursor()
    cursor.execute("SELECT * FROM match WHERE round_id=? ORDER BY match_number",
                   (round_id,))
    rows = cursor.fetchall()
    conn.close()
    return [Match(
        id=row["id"],
        tournament_id=row["tournament_id"],
        round_id=row["round_id"],
        match_number=row["match_number"],
        team1_id=row["team1_id"],
        team2_id=row["team2_id"],
        team1_score=row["team1_score"],
        team2_score=row["team2_score"],
        winner_id=row["winner_id"],
        status=MatchStatus(row["status"]),
        is_bye=bool(row["is_bye"]),
        bracket_side=row["bracket_side"],
        bracket_round=row["bracket_round"]
    ) for row in rows]


def get_matches_by_tournament(tournament_id: int) -> List[Match]:
    conn = get_connection()
    cursor = conn.cursor()
    cursor.execute("SELECT * FROM match WHERE tournament_id=? ORDER BY id",
                   (tournament_id,))
    rows = cursor.fetchall()
    conn.close()
    return [Match(
        id=row["id"],
        tournament_id=row["tournament_id"],
        round_id=row["round_id"],
        match_number=row["match_number"],
        team1_id=row["team1_id"],
        team2_id=row["team2_id"],
        team1_score=row["team1_score"],
        team2_score=row["team2_score"],
        winner_id=row["winner_id"],
        status=MatchStatus(row["status"]),
        is_bye=bool(row["is_bye"]),
        bracket_side=row["bracket_side"],
        bracket_round=row["bracket_round"]
    ) for row in rows]


def get_matches_by_bracket(tournament_id: int, bracket_round: str) -> List[Match]:
    conn = get_connection()
    cursor = conn.cursor()
    cursor.execute("""
    SELECT * FROM match WHERE tournament_id=? AND bracket_round=?
    ORDER BY bracket_side, match_number
    """, (tournament_id, bracket_round))
    rows = cursor.fetchall()
    conn.close()
    return [Match(
        id=row["id"],
        tournament_id=row["tournament_id"],
        round_id=row["round_id"],
        match_number=row["match_number"],
        team1_id=row["team1_id"],
        team2_id=row["team2_id"],
        team1_score=row["team1_score"],
        team2_score=row["team2_score"],
        winner_id=row["winner_id"],
        status=MatchStatus(row["status"]),
        is_bye=bool(row["is_bye"]),
        bracket_side=row["bracket_side"],
        bracket_round=row["bracket_round"]
    ) for row in rows]


def get_matchups_for_team(tournament_id: int, team_id: int) -> List[Dict[str, Any]]:
    conn = get_connection()
    cursor = conn.cursor()
    cursor.execute("""
    SELECT team1_id, team2_id, round_number
    FROM matchup_history
    WHERE tournament_id=? AND (team1_id=? OR team2_id=?)
    """, (tournament_id, team_id, team_id))
    rows = cursor.fetchall()
    conn.close()

    matchups = []
    for row in rows:
        opponent_id = row["team2_id"] if row["team1_id"] == team_id else row["team1_id"]
        matchups.append({
            "opponent_id": opponent_id,
            "round_number": row["round_number"]
        })
    return matchups


def get_all_matchup_pairs(tournament_id: int) -> set:
    conn = get_connection()
    cursor = conn.cursor()
    cursor.execute("""
    SELECT team1_id, team2_id FROM matchup_history WHERE tournament_id=?
    """, (tournament_id,))
    rows = cursor.fetchall()
    conn.close()

    pairs = set()
    for row in rows:
        t1, t2 = row["team1_id"], row["team2_id"]
        pairs.add(tuple(sorted((t1, t2))))
    return pairs


def update_match_result(match_id: int, team1_score: int, team2_score: int, winner_id: int) -> None:
    conn = get_connection()
    cursor = conn.cursor()
    cursor.execute("""
    UPDATE match SET team1_score=?, team2_score=?, winner_id=?, status=? WHERE id=?
    """, (team1_score, team2_score, winner_id, MatchStatus.COMPLETED.value, match_id))
    conn.commit()
    conn.close()


def update_match_teams(match_id: int, team1_id: Optional[int], team2_id: Optional[int]) -> None:
    conn = get_connection()
    cursor = conn.cursor()
    cursor.execute("""
    UPDATE match SET team1_id=?, team2_id=? WHERE id=?
    """, (team1_id, team2_id, match_id))
    conn.commit()
    conn.close()


def delete_matches_by_round(round_id: int) -> None:
    conn = get_connection()
    cursor = conn.cursor()
    cursor.execute("DELETE FROM match WHERE round_id=?", (round_id,))
    conn.commit()
    conn.close()


def check_round_complete(round_id: int) -> bool:
    conn = get_connection()
    cursor = conn.cursor()
    cursor.execute("""
    SELECT COUNT(*) as pending FROM match WHERE round_id=? AND status=?
    """, (round_id, MatchStatus.PENDING.value))
    row = cursor.fetchone()
    conn.close()
    return row["pending"] == 0

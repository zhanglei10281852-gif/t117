from typing import List, Optional, Dict, Any, Set, Tuple
from app.database.connection import get_connection
from app.database.crud_round import get_round
from app.models.models import Match, MatchStatus


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


def get_all_matchup_pairs(tournament_id: int) -> Set[Tuple[int, int]]:
    conn = get_connection()
    cursor = conn.cursor()
    cursor.execute("""
    SELECT team1_id, team2_id FROM matchup_history WHERE tournament_id=?
    """, (tournament_id,))
    rows = cursor.fetchall()
    conn.close()

    pairs: Set[Tuple[int, int]] = set()
    for row in rows:
        t1, t2 = row["team1_id"], row["team2_id"]
        pairs.add(tuple(sorted((t1, t2))))
    return pairs


def get_head_to_head_winner(tournament_id: int, team1_id: int, team2_id: int) -> Optional[int]:
    conn = get_connection()
    cursor = conn.cursor()
    cursor.execute("""
    SELECT m.winner_id
    FROM match m
    WHERE m.tournament_id=? AND m.status=?
    AND ((m.team1_id=? AND m.team2_id=?) OR (m.team1_id=? AND m.team2_id=?))
    ORDER BY m.id DESC
    LIMIT 1
    """, (tournament_id, MatchStatus.COMPLETED.value, team1_id, team2_id, team2_id, team1_id))
    row = cursor.fetchone()
    conn.close()
    if row and row["winner_id"]:
        return row["winner_id"]
    return None


def get_opponent_ids(tournament_id: int, team_id: int) -> List[int]:
    matchups = get_matchups_for_team(tournament_id, team_id)
    return [m["opponent_id"] for m in matchups]


def get_team_match_scores(tournament_id: int, team_id: int) -> Tuple[int, int]:
    conn = get_connection()
    cursor = conn.cursor()
    cursor.execute("""
    SELECT
        SUM(CASE WHEN team1_id=? THEN team1_score ELSE team2_score END) as scores_for,
        SUM(CASE WHEN team1_id=? THEN team2_score ELSE team1_score END) as scores_against
    FROM match
    WHERE tournament_id=? AND status=? AND is_bye=0
    AND (team1_id=? OR team2_id=?)
    """, (team_id, team_id, tournament_id, MatchStatus.COMPLETED.value, team_id, team_id))
    row = cursor.fetchone()
    conn.close()
    return (row["scores_for"] or 0, row["scores_against"] or 0)


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
    cursor.execute("DELETE FROM matchup_history WHERE match_id IN (SELECT id FROM match WHERE round_id=?)",
                   (round_id,))
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

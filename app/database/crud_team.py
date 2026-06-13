from typing import List, Optional
from app.database.connection import get_connection
from app.models.models import Team, TeamStatus


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

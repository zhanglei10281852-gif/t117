from typing import List, Optional
from app.database.connection import get_connection
from app.models.models import Tournament, TournamentPhase


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

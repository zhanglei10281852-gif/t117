from typing import List, Optional
from app.database.connection import get_connection
from app.models.models import Round, RoundStatus


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

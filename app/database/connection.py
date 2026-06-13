import sqlite3
import os
from pathlib import Path

DB_PATH = Path(__file__).resolve().parent.parent.parent / "data" / "tournament.db"


def get_connection():
    conn = sqlite3.connect(str(DB_PATH))
    conn.row_factory = sqlite3.Row
    conn.execute("PRAGMA foreign_keys = ON")
    return conn


def init_database():
    DB_PATH.parent.mkdir(parents=True, exist_ok=True)
    conn = get_connection()
    cursor = conn.cursor()
    cursor.executescript("""
    CREATE TABLE IF NOT EXISTS tournament (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        name TEXT NOT NULL,
        phase TEXT NOT NULL DEFAULT 'setup',
        current_round INTEGER DEFAULT 0,
        swiss_format TEXT DEFAULT 'bo1',
        playoff_format TEXT DEFAULT 'bo3',
        advance_wins INTEGER DEFAULT 3,
        eliminate_losses INTEGER DEFAULT 3,
        created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
    );

    CREATE TABLE IF NOT EXISTS team (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        tournament_id INTEGER NOT NULL,
        name TEXT NOT NULL,
        seed INTEGER NOT NULL,
        wins INTEGER DEFAULT 0,
        losses INTEGER DEFAULT 0,
        status TEXT DEFAULT 'active',
        has_bye INTEGER DEFAULT 0,
        eliminated_at_round INTEGER,
        FOREIGN KEY (tournament_id) REFERENCES tournament(id) ON DELETE CASCADE
    );

    CREATE TABLE IF NOT EXISTS round (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        tournament_id INTEGER NOT NULL,
        round_number INTEGER NOT NULL,
        phase TEXT NOT NULL,
        format TEXT NOT NULL,
        status TEXT DEFAULT 'pending',
        created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
    );

    CREATE TABLE IF NOT EXISTS match (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        tournament_id INTEGER NOT NULL,
        round_id INTEGER NOT NULL,
        match_number INTEGER NOT NULL,
        team1_id INTEGER,
        team2_id INTEGER,
        team1_score INTEGER DEFAULT 0,
        team2_score INTEGER DEFAULT 0,
        winner_id INTEGER,
        status TEXT DEFAULT 'pending',
        is_bye INTEGER DEFAULT 0,
        bracket_side TEXT,
        bracket_round TEXT,
        FOREIGN KEY (tournament_id) REFERENCES tournament(id) ON DELETE CASCADE,
        FOREIGN KEY (round_id) REFERENCES round(id) ON DELETE CASCADE,
        FOREIGN KEY (team1_id) REFERENCES team(id),
        FOREIGN KEY (team2_id) REFERENCES team(id),
        FOREIGN KEY (winner_id) REFERENCES team(id)
    );

    CREATE TABLE IF NOT EXISTS matchup_history (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        tournament_id INTEGER NOT NULL,
        team1_id INTEGER NOT NULL,
        team2_id INTEGER NOT NULL,
        match_id INTEGER NOT NULL,
        round_number INTEGER NOT NULL,
        FOREIGN KEY (tournament_id) REFERENCES tournament(id) ON DELETE CASCADE,
        FOREIGN KEY (team1_id) REFERENCES team(id),
        FOREIGN KEY (team2_id) REFERENCES team(id),
        FOREIGN KEY (match_id) REFERENCES match(id) ON DELETE CASCADE
    );

    CREATE INDEX IF NOT EXISTS idx_team_tournament ON team(tournament_id);
    CREATE INDEX IF NOT EXISTS idx_round_tournament ON round(tournament_id);
    CREATE INDEX IF NOT EXISTS idx_match_round ON match(round_id);
    CREATE INDEX IF NOT EXISTS idx_match_tournament ON match(tournament_id);
    CREATE INDEX IF NOT EXISTS idx_history_tournament ON matchup_history(tournament_id);
    """)
    conn.commit()
    conn.close()


def reset_database():
    if DB_PATH.exists():
        os.remove(str(DB_PATH))
    init_database()

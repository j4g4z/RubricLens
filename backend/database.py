"""SQLite database initialisation and CRUD operations for RubricLens."""

import sqlite3
import os
from typing import Optional

DB_PATH = os.path.join(os.path.dirname(os.path.dirname(__file__)), "rubriclens.db")


def get_connection(db_path: Optional[str] = None) -> sqlite3.Connection:
    """Get a SQLite connection with foreign keys enabled."""
    conn = sqlite3.connect(db_path or DB_PATH)
    conn.row_factory = sqlite3.Row
    conn.execute("PRAGMA foreign_keys = ON")
    return conn


def init_db(db_path: Optional[str] = None):
    """Initialise the SQLite database with schema."""
    conn = get_connection(db_path)
    cursor = conn.cursor()

    cursor.executescript("""
        CREATE TABLE IF NOT EXISTS rubric (
            rubric_id INTEGER PRIMARY KEY AUTOINCREMENT,
            title TEXT NOT NULL,
            total_marks REAL NOT NULL DEFAULT 0,
            created_at TEXT NOT NULL DEFAULT (datetime('now'))
        );

        CREATE TABLE IF NOT EXISTS criterion (
            criterion_id INTEGER PRIMARY KEY AUTOINCREMENT,
            rubric_id INTEGER NOT NULL,
            name TEXT NOT NULL,
            max_marks REAL NOT NULL DEFAULT 0,
            order_index INTEGER NOT NULL DEFAULT 0,
            FOREIGN KEY (rubric_id) REFERENCES rubric(rubric_id) ON DELETE CASCADE
        );

        CREATE TABLE IF NOT EXISTS level_descriptor (
            level_id INTEGER PRIMARY KEY AUTOINCREMENT,
            criterion_id INTEGER NOT NULL,
            level_num INTEGER NOT NULL,
            descriptor_text TEXT NOT NULL,
            FOREIGN KEY (criterion_id) REFERENCES criterion(criterion_id) ON DELETE CASCADE
        );

        CREATE TABLE IF NOT EXISTS submission (
            submission_id INTEGER PRIMARY KEY AUTOINCREMENT,
            rubric_id INTEGER NOT NULL,
            title TEXT NOT NULL DEFAULT 'Untitled Draft',
            raw_text TEXT NOT NULL,
            created_at TEXT NOT NULL DEFAULT (datetime('now')),
            FOREIGN KEY (rubric_id) REFERENCES rubric(rubric_id) ON DELETE CASCADE
        );

        CREATE TABLE IF NOT EXISTS text_chunk (
            chunk_id INTEGER PRIMARY KEY AUTOINCREMENT,
            submission_id INTEGER NOT NULL,
            chunk_text TEXT NOT NULL,
            start_offset INTEGER NOT NULL DEFAULT 0,
            end_offset INTEGER NOT NULL DEFAULT 0,
            FOREIGN KEY (submission_id) REFERENCES submission(submission_id) ON DELETE CASCADE
        );

        CREATE TABLE IF NOT EXISTS evidence_match (
            match_id INTEGER PRIMARY KEY AUTOINCREMENT,
            criterion_id INTEGER NOT NULL,
            chunk_id INTEGER NOT NULL,
            submission_id INTEGER NOT NULL,
            score REAL NOT NULL DEFAULT 0.0,
            snippet TEXT NOT NULL,
            FOREIGN KEY (criterion_id) REFERENCES criterion(criterion_id) ON DELETE CASCADE,
            FOREIGN KEY (chunk_id) REFERENCES text_chunk(chunk_id) ON DELETE CASCADE,
            FOREIGN KEY (submission_id) REFERENCES submission(submission_id) ON DELETE CASCADE
        );

        CREATE TABLE IF NOT EXISTS report_item (
            report_item_id INTEGER PRIMARY KEY AUTOINCREMENT,
            submission_id INTEGER NOT NULL,
            criterion_id INTEGER NOT NULL,
            status TEXT NOT NULL CHECK(status IN ('Missing', 'Partial', 'Strong')),
            rationale TEXT NOT NULL DEFAULT '',
            next_action TEXT NOT NULL DEFAULT '',
            evidence_strength REAL NOT NULL DEFAULT 0.0,
            generated_at TEXT NOT NULL DEFAULT (datetime('now')),
            FOREIGN KEY (submission_id) REFERENCES submission(submission_id) ON DELETE CASCADE,
            FOREIGN KEY (criterion_id) REFERENCES criterion(criterion_id) ON DELETE CASCADE
        );

        CREATE TABLE IF NOT EXISTS evaluation_run (
            run_id INTEGER PRIMARY KEY AUTOINCREMENT,
            submission_id INTEGER NOT NULL,
            method TEXT NOT NULL DEFAULT 'tfidf',
            notes TEXT,
            timestamp TEXT NOT NULL DEFAULT (datetime('now')),
            FOREIGN KEY (submission_id) REFERENCES submission(submission_id) ON DELETE CASCADE
        );
    """)

    conn.commit()
    conn.close()


# ---------------------------------------------------------------------------
# Rubric CRUD
# ---------------------------------------------------------------------------

def create_rubric(title: str, total_marks: float = 0, db_path: Optional[str] = None) -> int:
    """Create a new rubric and return its ID."""
    conn = get_connection(db_path)
    cursor = conn.execute(
        "INSERT INTO rubric (title, total_marks) VALUES (?, ?)",
        (title, total_marks),
    )
    rubric_id = cursor.lastrowid
    conn.commit()
    conn.close()
    return rubric_id


def get_rubric(rubric_id: int, db_path: Optional[str] = None) -> Optional[dict]:
    """Get a rubric with its criteria and descriptors."""
    conn = get_connection(db_path)
    row = conn.execute(
        "SELECT * FROM rubric WHERE rubric_id = ?", (rubric_id,)
    ).fetchone()
    if not row:
        conn.close()
        return None

    rubric = dict(row)
    criteria = conn.execute(
        "SELECT * FROM criterion WHERE rubric_id = ? ORDER BY order_index",
        (rubric_id,),
    ).fetchall()

    rubric["criteria"] = []
    for c in criteria:
        crit = dict(c)
        descriptors = conn.execute(
            "SELECT * FROM level_descriptor WHERE criterion_id = ? ORDER BY level_num",
            (c["criterion_id"],),
        ).fetchall()
        crit["descriptors"] = [dict(d) for d in descriptors]
        rubric["criteria"].append(crit)

    conn.close()
    return rubric


def list_rubrics(db_path: Optional[str] = None) -> list[dict]:
    """List all rubrics (without criteria details)."""
    conn = get_connection(db_path)
    rows = conn.execute(
        "SELECT rubric_id, title, total_marks, created_at FROM rubric ORDER BY created_at DESC"
    ).fetchall()
    conn.close()
    return [dict(r) for r in rows]


def delete_rubric(rubric_id: int, db_path: Optional[str] = None) -> bool:
    """Delete a rubric and all its associated data. Returns True if deleted."""
    conn = get_connection(db_path)
    cursor = conn.execute(
        "DELETE FROM rubric WHERE rubric_id = ?", (rubric_id,)
    )
    deleted = cursor.rowcount > 0
    conn.commit()
    conn.close()
    return deleted


def update_rubric(rubric_id: int, title: str, total_marks: float, db_path: Optional[str] = None) -> bool:
    """Update rubric title and total marks. Returns True if updated."""
    conn = get_connection(db_path)
    cursor = conn.execute(
        "UPDATE rubric SET title = ?, total_marks = ? WHERE rubric_id = ?",
        (title, total_marks, rubric_id),
    )
    updated = cursor.rowcount > 0
    conn.commit()
    conn.close()
    return updated


# ---------------------------------------------------------------------------
# Criterion CRUD
# ---------------------------------------------------------------------------

def add_criterion(
    rubric_id: int,
    name: str,
    max_marks: float = 0,
    order_index: int = 0,
    descriptors: Optional[list[dict]] = None,
    db_path: Optional[str] = None,
) -> int:
    """Add a criterion to a rubric. Optionally include descriptors.

    Each descriptor should be: {"level": int, "text": str}
    Returns the criterion_id.
    """
    conn = get_connection(db_path)
    cursor = conn.execute(
        "INSERT INTO criterion (rubric_id, name, max_marks, order_index) VALUES (?, ?, ?, ?)",
        (rubric_id, name, max_marks, order_index),
    )
    criterion_id = cursor.lastrowid

    if descriptors:
        for d in descriptors:
            conn.execute(
                "INSERT INTO level_descriptor (criterion_id, level_num, descriptor_text) VALUES (?, ?, ?)",
                (criterion_id, d["level"], d["text"]),
            )

    conn.commit()
    conn.close()
    return criterion_id


def delete_criterion(criterion_id: int, db_path: Optional[str] = None) -> bool:
    """Delete a criterion. Returns True if deleted."""
    conn = get_connection(db_path)
    cursor = conn.execute(
        "DELETE FROM criterion WHERE criterion_id = ?", (criterion_id,)
    )
    deleted = cursor.rowcount > 0
    conn.commit()
    conn.close()
    return deleted


# ---------------------------------------------------------------------------
# Submission CRUD
# ---------------------------------------------------------------------------

def create_submission(
    rubric_id: int,
    raw_text: str,
    title: str = "Untitled Draft",
    db_path: Optional[str] = None,
) -> int:
    """Create a new submission and return its ID."""
    conn = get_connection(db_path)
    cursor = conn.execute(
        "INSERT INTO submission (rubric_id, title, raw_text) VALUES (?, ?, ?)",
        (rubric_id, title, raw_text),
    )
    submission_id = cursor.lastrowid
    conn.commit()
    conn.close()
    return submission_id


def get_submission(submission_id: int, db_path: Optional[str] = None) -> Optional[dict]:
    """Get a submission by ID."""
    conn = get_connection(db_path)
    row = conn.execute(
        "SELECT * FROM submission WHERE submission_id = ?", (submission_id,)
    ).fetchone()
    conn.close()
    return dict(row) if row else None


def list_submissions(db_path: Optional[str] = None) -> list[dict]:
    """List all submissions."""
    conn = get_connection(db_path)
    rows = conn.execute(
        "SELECT submission_id, rubric_id, title, created_at FROM submission ORDER BY created_at DESC"
    ).fetchall()
    conn.close()
    return [dict(r) for r in rows]


def delete_submission(submission_id: int, db_path: Optional[str] = None) -> bool:
    """Delete a submission. Returns True if deleted."""
    conn = get_connection(db_path)
    cursor = conn.execute(
        "DELETE FROM submission WHERE submission_id = ?", (submission_id,)
    )
    deleted = cursor.rowcount > 0
    conn.commit()
    conn.close()
    return deleted


# ---------------------------------------------------------------------------
# Text Chunk CRUD
# ---------------------------------------------------------------------------

def save_chunks(submission_id: int, chunks: list[dict], db_path: Optional[str] = None):
    """Save text chunks for a submission. Clears existing chunks first.

    Each chunk: {"text": str, "start": int, "end": int}
    """
    conn = get_connection(db_path)
    conn.execute("DELETE FROM text_chunk WHERE submission_id = ?", (submission_id,))
    for chunk in chunks:
        conn.execute(
            "INSERT INTO text_chunk (submission_id, chunk_text, start_offset, end_offset) VALUES (?, ?, ?, ?)",
            (submission_id, chunk["text"], chunk["start"], chunk["end"]),
        )
    conn.commit()
    conn.close()


def get_chunks(submission_id: int, db_path: Optional[str] = None) -> list[dict]:
    """Get all text chunks for a submission."""
    conn = get_connection(db_path)
    rows = conn.execute(
        "SELECT * FROM text_chunk WHERE submission_id = ? ORDER BY start_offset",
        (submission_id,),
    ).fetchall()
    conn.close()
    return [dict(r) for r in rows]


# ---------------------------------------------------------------------------
# Evidence Match CRUD
# ---------------------------------------------------------------------------

def save_evidence_matches(
    submission_id: int,
    matches: list[dict],
    db_path: Optional[str] = None,
):
    """Save evidence matches for a submission. Clears existing matches first.

    Each match: {"criterion_id": int, "chunk_id": int, "score": float, "snippet": str}
    """
    conn = get_connection(db_path)
    conn.execute("DELETE FROM evidence_match WHERE submission_id = ?", (submission_id,))
    for m in matches:
        conn.execute(
            "INSERT INTO evidence_match (criterion_id, chunk_id, submission_id, score, snippet) VALUES (?, ?, ?, ?, ?)",
            (m["criterion_id"], m["chunk_id"], submission_id, m["score"], m["snippet"]),
        )
    conn.commit()
    conn.close()


def get_evidence_matches(
    submission_id: int,
    criterion_id: Optional[int] = None,
    db_path: Optional[str] = None,
) -> list[dict]:
    """Get evidence matches for a submission, optionally filtered by criterion."""
    conn = get_connection(db_path)
    if criterion_id:
        rows = conn.execute(
            "SELECT * FROM evidence_match WHERE submission_id = ? AND criterion_id = ? ORDER BY score DESC",
            (submission_id, criterion_id),
        ).fetchall()
    else:
        rows = conn.execute(
            "SELECT * FROM evidence_match WHERE submission_id = ? ORDER BY criterion_id, score DESC",
            (submission_id,),
        ).fetchall()
    conn.close()
    return [dict(r) for r in rows]


# ---------------------------------------------------------------------------
# Report Item CRUD
# ---------------------------------------------------------------------------

def save_report_items(
    submission_id: int,
    items: list[dict],
    db_path: Optional[str] = None,
):
    """Save report items for a submission. Clears existing items first.

    Each item: {"criterion_id": int, "status": str, "rationale": str,
                "next_action": str, "evidence_strength": float}
    """
    conn = get_connection(db_path)
    conn.execute("DELETE FROM report_item WHERE submission_id = ?", (submission_id,))
    for item in items:
        conn.execute(
            """INSERT INTO report_item
               (submission_id, criterion_id, status, rationale, next_action, evidence_strength)
               VALUES (?, ?, ?, ?, ?, ?)""",
            (
                submission_id,
                item["criterion_id"],
                item["status"],
                item["rationale"],
                item["next_action"],
                item["evidence_strength"],
            ),
        )
    conn.commit()
    conn.close()


def get_report_items(submission_id: int, db_path: Optional[str] = None) -> list[dict]:
    """Get all report items for a submission."""
    conn = get_connection(db_path)
    rows = conn.execute(
        "SELECT * FROM report_item WHERE submission_id = ? ORDER BY criterion_id",
        (submission_id,),
    ).fetchall()
    conn.close()
    return [dict(r) for r in rows]


# ---------------------------------------------------------------------------
# Evaluation Run CRUD
# ---------------------------------------------------------------------------

def create_evaluation_run(
    submission_id: int,
    method: str = "tfidf",
    notes: Optional[str] = None,
    db_path: Optional[str] = None,
) -> int:
    """Create an evaluation run record and return its ID."""
    conn = get_connection(db_path)
    cursor = conn.execute(
        "INSERT INTO evaluation_run (submission_id, method, notes) VALUES (?, ?, ?)",
        (submission_id, method, notes),
    )
    run_id = cursor.lastrowid
    conn.commit()
    conn.close()
    return run_id

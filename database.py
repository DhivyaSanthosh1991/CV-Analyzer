import sqlite3, os, base64, json
from datetime import datetime

DB_PATH = os.path.join(os.path.dirname(__file__), "workmoat.db")

def get_db():
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    return conn

def init_db():
    conn = get_db()
    for stmt in [
        """CREATE TABLE IF NOT EXISTS users (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            email TEXT UNIQUE NOT NULL, name TEXT,
            password_hash TEXT,
            created_at TEXT DEFAULT (datetime('now')),
            last_login TEXT)""",
        """CREATE TABLE IF NOT EXISTS otp_codes (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            email TEXT NOT NULL, code TEXT NOT NULL,
            expires_at TEXT NOT NULL, used INTEGER DEFAULT 0,
            created_at TEXT DEFAULT (datetime('now')))""",
        """CREATE TABLE IF NOT EXISTS cv_uploads (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            user_id INTEGER REFERENCES users(id),
            session_id TEXT, filename TEXT, file_type TEXT,
            file_size_kb REAL, file_b64 TEXT, extracted_text TEXT,
            job_title TEXT, industry TEXT,
            upload_source TEXT DEFAULT 'web',
            created_at TEXT DEFAULT (datetime('now')))""",
        """CREATE TABLE IF NOT EXISTS reports (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            user_id INTEGER REFERENCES users(id),
            cv_upload_id INTEGER REFERENCES cv_uploads(id),
            session_id TEXT UNIQUE NOT NULL,
            name TEXT, role TEXT,
            overall_score INTEGER, ai_susceptibility_score INTEGER,
            ai_augment_score INTEGER, automation_risk_level TEXT,
            automation_risk_timeline TEXT, full_result TEXT,
            pdf_b64 TEXT, paid INTEGER DEFAULT 0,
            created_at TEXT DEFAULT (datetime('now')))""",
        """CREATE TABLE IF NOT EXISTS roadmap_progress (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            user_id INTEGER REFERENCES users(id),
            report_id INTEGER REFERENCES reports(id),
            skill TEXT NOT NULL, priority TEXT,
            completed INTEGER DEFAULT 0, notes TEXT,
            updated_at TEXT DEFAULT (datetime('now')))""",
        "CREATE INDEX IF NOT EXISTS idx_reports_user   ON reports(user_id)",
        "CREATE INDEX IF NOT EXISTS idx_otp_email      ON otp_codes(email)",
        "CREATE INDEX IF NOT EXISTS idx_roadmap_user   ON roadmap_progress(user_id)",
        "CREATE INDEX IF NOT EXISTS idx_cv_user        ON cv_uploads(user_id)",
        "CREATE INDEX IF NOT EXISTS idx_cv_session     ON cv_uploads(session_id)",
    ]:
        conn.execute(stmt)
    conn.commit(); conn.close()

def migrate_db():
    conn = get_db()
    try:
        # users: password_hash
        cols = [r[1] for r in conn.execute("PRAGMA table_info(users)").fetchall()]
        if "password_hash" not in cols:
            conn.execute("ALTER TABLE users ADD COLUMN password_hash TEXT")
            print("Migrated: users.password_hash")

        # reports: cv_upload_id
        rcols = [r[1] for r in conn.execute("PRAGMA table_info(reports)").fetchall()]
        if "cv_upload_id" not in rcols:
            conn.execute("ALTER TABLE reports ADD COLUMN cv_upload_id INTEGER")
            print("Migrated: reports.cv_upload_id")

        # cv_uploads table
        tables = [r[0] for r in conn.execute("SELECT name FROM sqlite_master WHERE type='table'").fetchall()]
        if "cv_uploads" not in tables:
            conn.execute("""CREATE TABLE cv_uploads (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                user_id INTEGER REFERENCES users(id),
                session_id TEXT, filename TEXT, file_type TEXT,
                file_size_kb REAL, file_b64 TEXT, extracted_text TEXT,
                job_title TEXT, industry TEXT,
                upload_source TEXT DEFAULT 'web',
                created_at TEXT DEFAULT (datetime('now')))""")
            conn.execute("CREATE INDEX idx_cv_user    ON cv_uploads(user_id)")
            conn.execute("CREATE INDEX idx_cv_session ON cv_uploads(session_id)")
            print("Migrated: cv_uploads table created")

        conn.commit()
    except Exception as e:
        print(f"Migration: {e}")
    finally:
        conn.close()

# ── CV upload storage ─────────────────────────────────────────────────────────

def save_cv_upload(session_id, file_bytes, filename,
                   extracted_text, job_title="", industry="", user_id=None):
    """Store original file (base64) + extracted text. Returns cv_upload_id."""
    ext      = filename.rsplit(".", 1)[-1].lower() if "." in filename else "txt"
    file_b64 = base64.b64encode(file_bytes).decode()
    size_kb  = round(len(file_bytes) / 1024, 1)
    conn = get_db()
    try:
        conn.execute("""INSERT INTO cv_uploads
            (user_id, session_id, filename, file_type, file_size_kb,
             file_b64, extracted_text, job_title, industry)
            VALUES (?,?,?,?,?,?,?,?,?)""",
            (user_id, session_id, filename, ext, size_kb,
             file_b64, extracted_text[:8000], job_title, industry))
        conn.commit()
        row = conn.execute(
            "SELECT id FROM cv_uploads WHERE session_id=? ORDER BY id DESC LIMIT 1",
            (session_id,)).fetchone()
        return row["id"] if row else None
    finally:
        conn.close()

def save_cv_text(session_id, extracted_text,
                 job_title="", industry="", user_id=None):
    """Store pasted CV text (no file). Returns cv_upload_id."""
    conn = get_db()
    try:
        conn.execute("""INSERT INTO cv_uploads
            (user_id, session_id, filename, file_type, file_size_kb,
             file_b64, extracted_text, job_title, industry, upload_source)
            VALUES (?,?,?,?,?,?,?,?,?,?)""",
            (user_id, session_id, "pasted_cv.txt", "txt",
             round(len(extracted_text) / 1024, 1),
             "", extracted_text[:8000], job_title, industry, "paste"))
        conn.commit()
        row = conn.execute(
            "SELECT id FROM cv_uploads WHERE session_id=? ORDER BY id DESC LIMIT 1",
            (session_id,)).fetchone()
        return row["id"] if row else None
    finally:
        conn.close()

def get_user_cv_uploads(user_id):
    """List all CVs for a user (no file_b64 — fast)."""
    conn = get_db()
    try:
        rows = conn.execute("""
            SELECT c.id, c.session_id, c.filename, c.file_type,
                   c.file_size_kb, c.job_title, c.industry,
                   c.upload_source, c.created_at,
                   substr(c.extracted_text, 1, 200) as text_preview,
                   r.overall_score, r.ai_susceptibility_score,
                   r.automation_risk_level, r.paid as report_paid,
                   r.id as report_id
            FROM cv_uploads c
            LEFT JOIN reports r ON r.cv_upload_id = c.id
            WHERE c.user_id=?
            ORDER BY c.created_at DESC""", (user_id,)).fetchall()
        return [dict(r) for r in rows]
    finally:
        conn.close()

def get_cv_upload(upload_id, user_id):
    """Get full CV upload including file for download."""
    conn = get_db()
    try:
        row = conn.execute(
            "SELECT * FROM cv_uploads WHERE id=? AND user_id=?",
            (upload_id, user_id)).fetchone()
        return dict(row) if row else None
    finally:
        conn.close()

def delete_cv_upload(upload_id, user_id):
    """Delete a user's CV upload."""
    conn = get_db()
    try:
        conn.execute("DELETE FROM cv_uploads WHERE id=? AND user_id=?", (upload_id, user_id))
        conn.commit()
        return conn.total_changes > 0
    finally:
        conn.close()

def get_cv_storage_stats(user_id):
    """Storage usage stats for a user."""
    conn = get_db()
    try:
        row = conn.execute("""
            SELECT COUNT(*) as total_uploads,
                   ROUND(SUM(file_size_kb)/1024.0, 2) as total_mb,
                   MAX(created_at) as last_upload
            FROM cv_uploads WHERE user_id=?""", (user_id,)).fetchone()
        return dict(row) if row else {"total_uploads": 0, "total_mb": 0, "last_upload": None}
    finally:
        conn.close()

def link_cv_uploads_to_user(session_id, user_id):
    """Link anonymous CV uploads to user after they sign in."""
    conn = get_db()
    try:
        conn.execute("UPDATE cv_uploads SET user_id=? WHERE session_id=? AND user_id IS NULL",
                     (user_id, session_id))
        conn.commit()
    finally:
        conn.close()

# ── Reports ───────────────────────────────────────────────────────────────────

def save_report(session_id, result, paid=False, pdf_b64="",
                user_id=None, cv_upload_id=None):
    conn = get_db()
    try:
        conn.execute("""INSERT INTO reports
            (session_id, user_id, cv_upload_id, name, role, overall_score,
             ai_susceptibility_score, ai_augment_score,
             automation_risk_level, automation_risk_timeline,
             full_result, pdf_b64, paid)
            VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?)
            ON CONFLICT(session_id) DO UPDATE SET
                user_id=excluded.user_id,
                cv_upload_id=excluded.cv_upload_id,
                paid=excluded.paid, pdf_b64=excluded.pdf_b64,
                full_result=excluded.full_result""",
            (session_id, user_id, cv_upload_id,
             result.get("name",""), result.get("role",""),
             result.get("overall_score",0),
             result.get("ai_susceptibility_score",0),
             result.get("ai_augment_score",0),
             (result.get("automation_risk") or {}).get("level",""),
             (result.get("automation_risk") or {}).get("timeline",""),
             json.dumps(result), pdf_b64, 1 if paid else 0))
        conn.commit()
        return conn.execute("SELECT id FROM reports WHERE session_id=?",
                            (session_id,)).fetchone()["id"]
    finally:
        conn.close()

def get_user_reports(user_id):
    conn = get_db()
    try:
        rows = conn.execute("""SELECT id, session_id, name, role, overall_score,
            ai_susceptibility_score, ai_augment_score,
            automation_risk_level, automation_risk_timeline,
            paid, created_at
            FROM reports WHERE user_id=? ORDER BY created_at DESC""",
            (user_id,)).fetchall()
        return [dict(r) for r in rows]
    finally:
        conn.close()

def get_report_pdf(session_id, user_id):
    conn = get_db()
    try:
        row = conn.execute(
            "SELECT pdf_b64, name FROM reports WHERE session_id=? AND user_id=? AND paid=1",
            (session_id, user_id)).fetchone()
        return dict(row) if row else None
    finally:
        conn.close()

def link_report_to_user(session_id, user_id):
    conn = get_db()
    try:
        conn.execute("UPDATE reports SET user_id=? WHERE session_id=? AND user_id IS NULL",
                     (user_id, session_id))
        conn.commit()
    finally:
        conn.close()

def save_roadmap_progress(user_id, report_id, skills):
    conn = get_db()
    try:
        for skill in skills:
            if not conn.execute(
                "SELECT id FROM roadmap_progress WHERE user_id=? AND report_id=? AND skill=?",
                (user_id, report_id, skill["skill"])).fetchone():
                conn.execute(
                    "INSERT INTO roadmap_progress (user_id,report_id,skill,priority,completed) VALUES (?,?,?,?,0)",
                    (user_id, report_id, skill["skill"], skill.get("priority","medium")))
        conn.commit()
    finally:
        conn.close()

def toggle_roadmap_item(user_id, item_id, completed):
    conn = get_db()
    try:
        conn.execute("""UPDATE roadmap_progress SET completed=?, updated_at=datetime('now')
            WHERE id=? AND user_id=?""", (1 if completed else 0, item_id, user_id))
        conn.commit()
    finally:
        conn.close()

def get_roadmap_progress(user_id, report_id):
    conn = get_db()
    try:
        rows = conn.execute("""SELECT id, skill, priority, completed, notes, updated_at
            FROM roadmap_progress WHERE user_id=? AND report_id=?
            ORDER BY CASE priority WHEN 'high' THEN 1 WHEN 'medium' THEN 2 ELSE 3 END""",
            (user_id, report_id)).fetchall()
        return [dict(r) for r in rows]
    finally:
        conn.close()

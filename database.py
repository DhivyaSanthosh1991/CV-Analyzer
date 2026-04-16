"""
WorkMoat database — PostgreSQL via Supabase
Falls back to SQLite for local dev if DATABASE_URL is not set.
"""
import os, base64, json
from datetime import datetime
from contextlib import contextmanager

DATABASE_URL = os.getenv("DATABASE_URL", "")  # Set this in Render env vars

# ── Connection pool ───────────────────────────────────────────────────────────
if DATABASE_URL:
    import psycopg2
    import psycopg2.extras
    from psycopg2 import pool as pg_pool

    _pool = None

    def _get_pool():
        global _pool
        if _pool is None:
            _pool = pg_pool.SimpleConnectionPool(
                1, 10,
                DATABASE_URL,
                sslmode="require",
                cursor_factory=psycopg2.extras.RealDictCursor
            )
        return _pool

    @contextmanager
    def get_db():
        pool = _get_pool()
        conn = pool.getconn()
        try:
            yield conn
            conn.commit()
        except Exception:
            conn.rollback()
            raise
        finally:
            pool.putconn(conn)

    def _exec(sql, params=(), fetchone=False, fetchall=False):
        with get_db() as conn:
            cur = conn.cursor()
            cur.execute(sql, params)
            if fetchone:  return cur.fetchone()
            if fetchall:  return cur.fetchall()
            return cur.rowcount

    PLACEHOLDER = "%s"
    AUTOINCREMENT = "SERIAL PRIMARY KEY"
    TEXT_PK = ""
    UPSERT_REPORTS = """
        INSERT INTO reports
            (session_id, user_id, cv_upload_id, name, role, overall_score,
             ai_susceptibility_score, ai_augment_score,
             automation_risk_level, automation_risk_timeline,
             full_result, pdf_b64, paid)
        VALUES (%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s)
        ON CONFLICT(session_id) DO UPDATE SET
            user_id=EXCLUDED.user_id,
            cv_upload_id=EXCLUDED.cv_upload_id,
            paid=EXCLUDED.paid,
            pdf_b64=EXCLUDED.pdf_b64,
            full_result=EXCLUDED.full_result
        RETURNING id
    """

else:
    # ── SQLite fallback for local dev ─────────────────────────────────────────
    import sqlite3

    DB_PATH = os.path.join(os.path.dirname(__file__), "workmoat.db")

    @contextmanager
    def get_db():
        conn = sqlite3.connect(DB_PATH)
        conn.row_factory = sqlite3.Row
        try:
            yield conn
            conn.commit()
        except Exception:
            conn.rollback()
            raise
        finally:
            conn.close()

    def _exec(sql, params=(), fetchone=False, fetchall=False):
        with get_db() as conn:
            cur = conn.execute(sql, params)
            if fetchone:  return cur.fetchone()
            if fetchall:  return cur.fetchall()
            return conn.total_changes

    PLACEHOLDER = "?"
    AUTOINCREMENT = "INTEGER PRIMARY KEY AUTOINCREMENT"
    UPSERT_REPORTS = """
        INSERT INTO reports
            (session_id, user_id, cv_upload_id, name, role, overall_score,
             ai_susceptibility_score, ai_augment_score,
             automation_risk_level, automation_risk_timeline,
             full_result, pdf_b64, paid)
        VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?)
        ON CONFLICT(session_id) DO UPDATE SET
            user_id=excluded.user_id,
            cv_upload_id=excluded.cv_upload_id,
            paid=excluded.paid,
            pdf_b64=excluded.pdf_b64,
            full_result=excluded.full_result
    """


def _row(r):
    """Convert DB row to dict safely."""
    if r is None: return None
    return dict(r)

def _rows(rs):
    return [dict(r) for r in (rs or [])]


# ── Schema init ───────────────────────────────────────────────────────────────

def init_db():
    P = PLACEHOLDER
    stmts = [
        f"""CREATE TABLE IF NOT EXISTS users (
            id            {'SERIAL PRIMARY KEY' if DATABASE_URL else 'INTEGER PRIMARY KEY AUTOINCREMENT'},
            email         TEXT UNIQUE NOT NULL,
            name          TEXT,
            password_hash TEXT,
            created_at    TEXT DEFAULT (datetime('now')),
            last_login    TEXT
        )""",
        f"""CREATE TABLE IF NOT EXISTS otp_codes (
            id         {'SERIAL PRIMARY KEY' if DATABASE_URL else 'INTEGER PRIMARY KEY AUTOINCREMENT'},
            email      TEXT NOT NULL,
            code       TEXT NOT NULL,
            expires_at TEXT NOT NULL,
            used       INTEGER DEFAULT 0,
            created_at TIMESTAMP DEFAULT NOW()
        )""",
        f"""CREATE TABLE IF NOT EXISTS cv_uploads (
            id             {'SERIAL PRIMARY KEY' if DATABASE_URL else 'INTEGER PRIMARY KEY AUTOINCREMENT'},
            user_id        INTEGER REFERENCES users(id),
            session_id     TEXT,
            filename       TEXT,
            file_type      TEXT,
            file_size_kb   REAL,
            file_b64       TEXT,
            extracted_text TEXT,
            job_title      TEXT,
            industry       TEXT,
            upload_source  TEXT DEFAULT 'web',
            created_at     TEXT DEFAULT (datetime('now'))
        )""",
        f"""CREATE TABLE IF NOT EXISTS reports (
            id                       {'SERIAL PRIMARY KEY' if DATABASE_URL else 'INTEGER PRIMARY KEY AUTOINCREMENT'},
            user_id                  INTEGER REFERENCES users(id),
            cv_upload_id             INTEGER REFERENCES cv_uploads(id),
            session_id               TEXT UNIQUE NOT NULL,
            name                     TEXT,
            role                     TEXT,
            overall_score            INTEGER,
            ai_susceptibility_score  INTEGER,
            ai_augment_score         INTEGER,
            automation_risk_level    TEXT,
            automation_risk_timeline TEXT,
            full_result              TEXT,
            pdf_b64                  TEXT,
            paid                     INTEGER DEFAULT 0,
            created_at               TIMESTAMP DEFAULT NOW()
        )""",
        f"""CREATE TABLE IF NOT EXISTS roadmap_progress (
            id         {'SERIAL PRIMARY KEY' if DATABASE_URL else 'INTEGER PRIMARY KEY AUTOINCREMENT'},
            user_id    INTEGER REFERENCES users(id),
            report_id  INTEGER REFERENCES reports(id),
            skill      TEXT NOT NULL,
            priority   TEXT,
            completed  INTEGER DEFAULT 0,
            notes      TEXT,
            updated_at TEXT DEFAULT (datetime('now'))
        )""",
        "CREATE INDEX IF NOT EXISTS idx_reports_user   ON reports(user_id)",
        "CREATE INDEX IF NOT EXISTS idx_otp_email      ON otp_codes(email)",
        "CREATE INDEX IF NOT EXISTS idx_roadmap_user   ON roadmap_progress(user_id)",
        "CREATE INDEX IF NOT EXISTS idx_cv_user        ON cv_uploads(user_id)",
        "CREATE INDEX IF NOT EXISTS idx_cv_session     ON cv_uploads(session_id)",
    ]
    with get_db() as conn:
        if DATABASE_URL:
            cur = conn.cursor()
            for stmt in stmts:
                try:
                    cur.execute(stmt)
                except Exception as e:
                    print(f"init_db note: {e}")
        else:
            for stmt in stmts:
                try:
                    conn.execute(stmt)
                except Exception as e:
                    print(f"init_db note: {e}")
    print("DB initialised OK")


def migrate_db():
    """Safe column migrations — runs on every startup."""
    migrations = [
        ("users",   "password_hash", "TEXT"),
        ("reports", "cv_upload_id",  "INTEGER"),
    ]
    with get_db() as conn:
        for table, col, dtype in migrations:
            try:
                if DATABASE_URL:
                    cur = conn.cursor()
                    cur.execute(f"""
                        ALTER TABLE {table} ADD COLUMN IF NOT EXISTS {col} {dtype}
                    """)
                else:
                    cols = [r[1] for r in conn.execute(f"PRAGMA table_info({table})").fetchall()]
                    if col not in cols:
                        conn.execute(f"ALTER TABLE {table} ADD COLUMN {col} {dtype}")
                        print(f"Migrated: {table}.{col}")
            except Exception as e:
                print(f"Migration note {table}.{col}: {e}")
    print("Migrations OK")


# ── CV uploads ────────────────────────────────────────────────────────────────

def save_cv_upload(session_id, file_bytes, filename,
                   extracted_text, job_title="", industry="", user_id=None):
    ext      = filename.rsplit(".", 1)[-1].lower() if "." in filename else "txt"
    file_b64 = base64.b64encode(file_bytes).decode()
    size_kb  = round(len(file_bytes) / 1024, 1)
    P = PLACEHOLDER
    sql = f"""INSERT INTO cv_uploads
        (user_id,session_id,filename,file_type,file_size_kb,
         file_b64,extracted_text,job_title,industry)
        VALUES ({P},{P},{P},{P},{P},{P},{P},{P},{P})"""
    if DATABASE_URL:
        sql += " RETURNING id"
        row = _exec(sql, (user_id, session_id, filename, ext, size_kb,
                          file_b64, extracted_text[:8000], job_title, industry), fetchone=True)
        return row["id"] if row else None
    else:
        _exec(sql, (user_id, session_id, filename, ext, size_kb,
                    file_b64, extracted_text[:8000], job_title, industry))
        row = _exec(f"SELECT id FROM cv_uploads WHERE session_id={P} ORDER BY id DESC LIMIT 1",
                    (session_id,), fetchone=True)
        return row["id"] if row else None


def save_cv_text(session_id, extracted_text,
                 job_title="", industry="", user_id=None):
    P = PLACEHOLDER
    sql = f"""INSERT INTO cv_uploads
        (user_id,session_id,filename,file_type,file_size_kb,
         file_b64,extracted_text,job_title,industry,upload_source)
        VALUES ({P},{P},{P},{P},{P},{P},{P},{P},{P},{P})"""
    params = (user_id, session_id, "pasted_cv.txt", "txt",
              round(len(extracted_text)/1024, 1),
              "", extracted_text[:8000], job_title, industry, "paste")
    if DATABASE_URL:
        row = _exec(sql + " RETURNING id", params, fetchone=True)
        return row["id"] if row else None
    else:
        _exec(sql, params)
        row = _exec(f"SELECT id FROM cv_uploads WHERE session_id={P} ORDER BY id DESC LIMIT 1",
                    (session_id,), fetchone=True)
        return row["id"] if row else None


def get_user_cv_uploads(user_id):
    P = PLACEHOLDER
    rows = _exec(f"""
        SELECT c.id, c.session_id, c.filename, c.file_type,
               c.file_size_kb, c.job_title, c.industry,
               c.upload_source, c.created_at,
               SUBSTRING(c.extracted_text, 1, 200) as text_preview,
               r.overall_score, r.ai_susceptibility_score,
               r.automation_risk_level, r.paid as report_paid, r.id as report_id
        FROM cv_uploads c
        LEFT JOIN reports r ON r.cv_upload_id = c.id
        WHERE c.user_id={P}
        ORDER BY c.created_at DESC""", (user_id,), fetchall=True)
    return _rows(rows)


def get_cv_upload(upload_id, user_id):
    P = PLACEHOLDER
    return _row(_exec(f"SELECT * FROM cv_uploads WHERE id={P} AND user_id={P}",
                      (upload_id, user_id), fetchone=True))


def delete_cv_upload(upload_id, user_id):
    P = PLACEHOLDER
    return _exec(f"DELETE FROM cv_uploads WHERE id={P} AND user_id={P}",
                 (upload_id, user_id)) > 0


def get_cv_storage_stats(user_id):
    P = PLACEHOLDER
    row = _exec(f"""SELECT COUNT(*) as total_uploads,
        ROUND(SUM(file_size_kb)/1024.0, 2) as total_mb,
        MAX(created_at) as last_upload
        FROM cv_uploads WHERE user_id={P}""", (user_id,), fetchone=True)
    return _row(row) or {"total_uploads": 0, "total_mb": 0, "last_upload": None}


# ── Reports ───────────────────────────────────────────────────────────────────

def save_report(session_id, result, paid=False, pdf_b64="",
                user_id=None, cv_upload_id=None):
    P = PLACEHOLDER
    params = (
        session_id, user_id, cv_upload_id,
        result.get("name",""), result.get("role",""),
        result.get("overall_score", 0),
        result.get("ai_susceptibility_score", 0),
        result.get("ai_augment_score", 0),
        (result.get("automation_risk") or {}).get("level",""),
        (result.get("automation_risk") or {}).get("timeline",""),
        json.dumps(result), pdf_b64, 1 if paid else 0
    )
    if DATABASE_URL:
        row = _exec(UPSERT_REPORTS, params, fetchone=True)
        return row["id"] if row else None
    else:
        _exec(UPSERT_REPORTS, params)
        row = _exec(f"SELECT id FROM reports WHERE session_id={P}",
                    (session_id,), fetchone=True)
        return row["id"] if row else None


def get_user_reports(user_id):
    P = PLACEHOLDER
    rows = _exec(f"""SELECT id, session_id, name, role, overall_score,
        ai_susceptibility_score, ai_augment_score,
        automation_risk_level, automation_risk_timeline, paid, created_at
        FROM reports WHERE user_id={P} ORDER BY created_at DESC""",
        (user_id,), fetchall=True)
    return _rows(rows)


def get_report_pdf(session_id, user_id):
    P = PLACEHOLDER
    return _row(_exec(
        f"SELECT pdf_b64, name FROM reports WHERE session_id={P} AND user_id={P} AND paid=1",
        (session_id, user_id), fetchone=True))


def link_items_to_user(session_id, user_id):
    P = PLACEHOLDER
    _exec(f"UPDATE reports   SET user_id={P} WHERE session_id={P} AND user_id IS NULL", (user_id, session_id))
    _exec(f"UPDATE cv_uploads SET user_id={P} WHERE session_id={P} AND user_id IS NULL", (user_id, session_id))


# ── Roadmap ───────────────────────────────────────────────────────────────────

def save_roadmap_progress(user_id, report_id, skills):
    P = PLACEHOLDER
    for skill in skills:
        exists = _exec(
            f"SELECT id FROM roadmap_progress WHERE user_id={P} AND report_id={P} AND skill={P}",
            (user_id, report_id, skill["skill"]), fetchone=True)
        if not exists:
            _exec(f"INSERT INTO roadmap_progress (user_id,report_id,skill,priority,completed) VALUES ({P},{P},{P},{P},0)",
                  (user_id, report_id, skill["skill"], skill.get("priority","medium")))


def toggle_roadmap_item(user_id, item_id, completed):
    P = PLACEHOLDER
    now_expr = "NOW()" if DATABASE_URL else "datetime('now')"
    _exec(f"UPDATE roadmap_progress SET completed={P}, updated_at={now_expr} WHERE id={P} AND user_id={P}",
          (1 if completed else 0, item_id, user_id))


def get_roadmap_progress(user_id, report_id):
    P = PLACEHOLDER
    rows = _exec(f"""SELECT id, skill, priority, completed, notes, updated_at
        FROM roadmap_progress WHERE user_id={P} AND report_id={P}
        ORDER BY CASE priority WHEN 'high' THEN 1 WHEN 'medium' THEN 2 ELSE 3 END""",
        (user_id, report_id), fetchall=True)
    return _rows(rows)


# ── OTP helpers (used by auth.py) ─────────────────────────────────────────────

def store_otp_db(email, code, expires):
    P = PLACEHOLDER
    _exec(f"UPDATE otp_codes SET used=1 WHERE email={P}", (email,))
    _exec(f"INSERT INTO otp_codes (email,code,expires_at) VALUES ({P},{P},{P})", (email, code, expires))


def get_latest_otp(email):
    P = PLACEHOLDER
    return _row(_exec(
        f"SELECT id,code,expires_at FROM otp_codes WHERE email={P} AND used=0 ORDER BY created_at DESC LIMIT 1",
        (email,), fetchone=True))


def mark_otp_used(otp_id):
    P = PLACEHOLDER
    _exec(f"UPDATE otp_codes SET used=1 WHERE id={P}", (otp_id,))


# ── User helpers (used by auth.py) ────────────────────────────────────────────

def get_user_by_email(email):
    P = PLACEHOLDER
    return _row(_exec(f"SELECT * FROM users WHERE email={P}", (email,), fetchone=True))


def get_user_by_id(user_id):
    P = PLACEHOLDER
    return _row(_exec(f"SELECT id,email,name,created_at FROM users WHERE id={P}", (user_id,), fetchone=True))


def create_user(email, name, pw_hash):
    P = PLACEHOLDER
    if DATABASE_URL:
        row = _exec(
            f"INSERT INTO users (email,name,password_hash,last_login) VALUES ({P},{P},{P},NOW()) RETURNING id",
            (email, name, pw_hash), fetchone=True)
        return row["id"] if row else None
    else:
        _exec(f"INSERT INTO users (email,name,password_hash,last_login) VALUES ({P},{P},{P},datetime('now'))",
              (email, name, pw_hash))
        row = _exec(f"SELECT id FROM users WHERE email={P}", (email,), fetchone=True)
        return row["id"] if row else None


def update_user(user_id, name=None, pw_hash=None):
    P = PLACEHOLDER
    now = "NOW()" if DATABASE_URL else "datetime('now')"
    if pw_hash:
        _exec(f"UPDATE users SET name={P}, password_hash={P}, last_login={now} WHERE id={P}",
              (name, pw_hash, user_id))
    else:
        _exec(f"UPDATE users SET name={P}, last_login={now} WHERE id={P}", (name, user_id))

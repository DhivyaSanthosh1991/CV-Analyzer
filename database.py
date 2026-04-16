"""
WorkMoat — SQLite database
Supports optional PostgreSQL via DATABASE_URL env var (Supabase).
"""
import os, base64, json, sqlite3
from contextlib import contextmanager

DATABASE_URL = os.getenv("DATABASE_URL", "")

# ── PostgreSQL (Supabase) ─────────────────────────────────────────────────────
if DATABASE_URL:
    import psycopg2, psycopg2.extras
    from psycopg2 import pool as pgpool

    _pool = None

    def _get_pool():
        global _pool
        if _pool is None:
            _pool = pgpool.SimpleConnectionPool(
                1, 5, DATABASE_URL, sslmode="require",
                cursor_factory=psycopg2.extras.RealDictCursor)
        return _pool

    @contextmanager
    def _conn():
        p = _get_pool(); c = p.getconn()
        try:
            yield c; c.commit()
        except:
            c.rollback(); raise
        finally:
            p.putconn(c)

    PH = "%s"

    def _q(sql, params=(), one=False, many=False):
        with _conn() as c:
            cur = c.cursor()
            cur.execute(sql, params or ())
            if one:  r = cur.fetchone(); return dict(r) if r else None
            if many: return [dict(r) for r in cur.fetchall()]
            try: return cur.fetchone()
            except: return None

    def _last_id(cur, table):
        cur.execute(f"SELECT lastval()")
        return cur.fetchone()[0]

    NOW = "NOW()"
    SUBSTR = "SUBSTRING"

# ── SQLite (default / local dev) ──────────────────────────────────────────────
else:
    # Use /tmp on Render (survives within deployment, cleared on redeploy)
    # Use local file for dev
    if os.path.exists("/tmp"):
        DB_PATH = "/tmp/workmoat.db"
    else:
        DB_PATH = os.path.join(os.path.dirname(__file__), "workmoat.db")

    @contextmanager
    def _conn():
        c = sqlite3.connect(DB_PATH)
        c.row_factory = sqlite3.Row
        try:
            yield c; c.commit()
        except:
            c.rollback(); raise
        finally:
            c.close()

    PH = "?"

    def _q(sql, params=(), one=False, many=False):
        with _conn() as c:
            cur = c.execute(sql, params or ())
            if one:  r = cur.fetchone(); return dict(r) if r else None
            if many: return [dict(r) for r in cur.fetchall()]
            return None

    NOW = "datetime('now')"
    SUBSTR = "substr"


def _rows(rs):
    return [dict(r) for r in (rs or [])]

def _row(r):
    return dict(r) if r else None


# ── Schema ────────────────────────────────────────────────────────────────────
def init_db():
    if DATABASE_URL:
        serial = "SERIAL PRIMARY KEY"
        ts_now = "TIMESTAMP DEFAULT NOW()"
        ts     = "TIMESTAMP"
    else:
        serial = "INTEGER PRIMARY KEY AUTOINCREMENT"
        ts_now = "TEXT DEFAULT (datetime('now'))"
        ts     = "TEXT"
    stmts  = [
        f"""CREATE TABLE IF NOT EXISTS users (
            id {serial}, email TEXT UNIQUE NOT NULL, name TEXT,
            password_hash TEXT, created_at {ts_now}, last_login {ts})""",
        f"""CREATE TABLE IF NOT EXISTS otp_codes (
            id {serial}, email TEXT NOT NULL, code TEXT NOT NULL,
            expires_at TEXT NOT NULL, used INTEGER DEFAULT 0,
            created_at {ts_now})""",
        f"""CREATE TABLE IF NOT EXISTS cv_uploads (
            id {serial}, user_id INTEGER REFERENCES users(id),
            session_id TEXT, filename TEXT, file_type TEXT, file_size_kb REAL,
            file_b64 TEXT, extracted_text TEXT, job_title TEXT, industry TEXT,
            upload_source TEXT DEFAULT 'web', created_at {ts_now})""",
        f"""CREATE TABLE IF NOT EXISTS reports (
            id {serial}, user_id INTEGER REFERENCES users(id),
            cv_upload_id INTEGER, session_id TEXT UNIQUE NOT NULL,
            name TEXT, role TEXT, overall_score INTEGER,
            ai_susceptibility_score INTEGER, ai_augment_score INTEGER,
            automation_risk_level TEXT, automation_risk_timeline TEXT,
            full_result TEXT, pdf_b64 TEXT, paid INTEGER DEFAULT 0,
            created_at {ts_now})""",
        f"""CREATE TABLE IF NOT EXISTS roadmap_progress (
            id {serial}, user_id INTEGER REFERENCES users(id),
            report_id INTEGER REFERENCES reports(id),
            skill TEXT NOT NULL, priority TEXT, completed INTEGER DEFAULT 0,
            notes TEXT, updated_at {ts_now})""",
        "CREATE INDEX IF NOT EXISTS idx_reports_user ON reports(user_id)",
        "CREATE INDEX IF NOT EXISTS idx_otp_email    ON otp_codes(email)",
        "CREATE INDEX IF NOT EXISTS idx_roadmap_user ON roadmap_progress(user_id)",
        "CREATE INDEX IF NOT EXISTS idx_cv_user      ON cv_uploads(user_id)",
        "CREATE INDEX IF NOT EXISTS idx_cv_session   ON cv_uploads(session_id)",
    ]
    if DATABASE_URL:
        with _conn() as c:
            for s in stmts:
                try: c.cursor().execute(s)
                except Exception as e:
                    if "already exists" not in str(e).lower(): print(f"init note: {e}")
    else:
        c = sqlite3.connect(DB_PATH)
        c.isolation_level = None  # autocommit for DDL
        for s in stmts:
            try: c.execute(s)
            except Exception as e:
                if "already exists" not in str(e).lower(): print(f"init note: {e}")
        c.close()
    print("DB ready")


def migrate_db():
    cols_to_add = [
        ("users",   "password_hash", "TEXT"),
        ("reports", "cv_upload_id",  "INTEGER"),
    ]
    with _conn() as c:
        for table, col, dtype in cols_to_add:
            try:
                if DATABASE_URL:
                    c.cursor().execute(f"ALTER TABLE {table} ADD COLUMN IF NOT EXISTS {col} {dtype}")
                else:
                    existing = [r[1] for r in c.execute(f"PRAGMA table_info({table})")]
                    if col not in existing:
                        c.execute(f"ALTER TABLE {table} ADD COLUMN {col} {dtype}")
            except Exception as e:
                pass
    print("Migrations OK")


# ── Users ─────────────────────────────────────────────────────────────────────
def get_user_by_email(email):
    return _q(f"SELECT * FROM users WHERE email={PH}", (email,), one=True)

def get_user_by_id(uid):
    return _q(f"SELECT id,email,name,created_at FROM users WHERE id={PH}", (uid,), one=True)

def create_user(email, name, pw_hash):
    if DATABASE_URL:
        r = _q(f"INSERT INTO users (email,name,password_hash,last_login) VALUES ({PH},{PH},{PH},{NOW}) RETURNING id",
               (email, name, pw_hash), one=True)
        return r["id"] if r else None
    else:
        with _conn() as c:
            c.execute(f"INSERT INTO users (email,name,password_hash,last_login) VALUES ({PH},{PH},{PH},{NOW})",
                      (email, name, pw_hash))
            return c.execute("SELECT last_insert_rowid()").fetchone()[0]

def update_user(uid, name=None, pw_hash=None):
    if pw_hash:
        _q(f"UPDATE users SET name={PH}, password_hash={PH}, last_login={NOW} WHERE id={PH}",
           (name, pw_hash, uid))
    else:
        _q(f"UPDATE users SET last_login={NOW} WHERE id={PH}", (uid,))


# ── OTP ───────────────────────────────────────────────────────────────────────
def store_otp_db(email, code, expires):
    _q(f"UPDATE otp_codes SET used=1 WHERE email={PH}", (email,))
    _q(f"INSERT INTO otp_codes (email,code,expires_at) VALUES ({PH},{PH},{PH})",
       (email, code, expires))

def get_latest_otp(email):
    return _q(f"SELECT id,code,expires_at FROM otp_codes WHERE email={PH} AND used=0 ORDER BY created_at DESC LIMIT 1",
              (email,), one=True)

def mark_otp_used(otp_id):
    _q(f"UPDATE otp_codes SET used=1 WHERE id={PH}", (otp_id,))


# ── CV uploads ────────────────────────────────────────────────────────────────
def save_cv_upload(session_id, file_bytes, filename, extracted_text,
                   job_title="", industry="", user_id=None):
    ext      = filename.rsplit(".", 1)[-1].lower() if "." in filename else "txt"
    file_b64 = base64.b64encode(file_bytes).decode()
    size_kb  = round(len(file_bytes) / 1024, 1)
    sql = f"""INSERT INTO cv_uploads
        (user_id,session_id,filename,file_type,file_size_kb,file_b64,extracted_text,job_title,industry)
        VALUES ({PH},{PH},{PH},{PH},{PH},{PH},{PH},{PH},{PH})"""
    params = (user_id, session_id, filename, ext, size_kb,
              file_b64, extracted_text[:8000], job_title, industry)
    if DATABASE_URL:
        r = _q(sql + " RETURNING id", params, one=True)
        return r["id"] if r else None
    else:
        with _conn() as c:
            c.execute(sql, params)
            r = c.execute(f"SELECT id FROM cv_uploads WHERE session_id={PH} ORDER BY id DESC LIMIT 1",
                          (session_id,)).fetchone()
            return r[0] if r else None

def save_cv_text(session_id, extracted_text, job_title="", industry="", user_id=None):
    sql = f"""INSERT INTO cv_uploads
        (user_id,session_id,filename,file_type,file_size_kb,file_b64,extracted_text,job_title,industry,upload_source)
        VALUES ({PH},{PH},{PH},{PH},{PH},{PH},{PH},{PH},{PH},{PH})"""
    params = (user_id, session_id, "pasted_cv.txt", "txt",
              round(len(extracted_text)/1024,1), "", extracted_text[:8000],
              job_title, industry, "paste")
    if DATABASE_URL:
        r = _q(sql + " RETURNING id", params, one=True)
        return r["id"] if r else None
    else:
        with _conn() as c:
            c.execute(sql, params)
            r = c.execute(f"SELECT id FROM cv_uploads WHERE session_id={PH} ORDER BY id DESC LIMIT 1",
                          (session_id,)).fetchone()
            return r[0] if r else None

def get_user_cv_uploads(user_id):
    return _q(f"""SELECT c.id, c.session_id, c.filename, c.file_type, c.file_size_kb,
        c.job_title, c.industry, c.upload_source, c.created_at,
        {SUBSTR}(c.extracted_text,1,200) as text_preview,
        r.overall_score, r.ai_susceptibility_score,
        r.automation_risk_level, r.paid as report_paid, r.id as report_id
        FROM cv_uploads c LEFT JOIN reports r ON r.cv_upload_id=c.id
        WHERE c.user_id={PH} ORDER BY c.created_at DESC""", (user_id,), many=True)

def get_cv_upload(upload_id, user_id):
    return _q(f"SELECT * FROM cv_uploads WHERE id={PH} AND user_id={PH}",
              (upload_id, user_id), one=True)

def delete_cv_upload(upload_id, user_id):
    with _conn() as c:
        if DATABASE_URL:
            cur = c.cursor()
            cur.execute(f"DELETE FROM cv_uploads WHERE id={PH} AND user_id={PH}", (upload_id, user_id))
            return cur.rowcount > 0
        else:
            c.execute(f"DELETE FROM cv_uploads WHERE id={PH} AND user_id={PH}", (upload_id, user_id))
            return c.total_changes > 0

def get_cv_storage_stats(user_id):
    r = _q(f"""SELECT COUNT(*) as total_uploads,
        ROUND(SUM(file_size_kb)/1024.0,2) as total_mb,
        MAX(created_at) as last_upload
        FROM cv_uploads WHERE user_id={PH}""", (user_id,), one=True)
    return r or {"total_uploads": 0, "total_mb": 0, "last_upload": None}


# ── Reports ───────────────────────────────────────────────────────────────────
def save_report(session_id, result, paid=False, pdf_b64="",
                user_id=None, cv_upload_id=None):
    params = (session_id, user_id, cv_upload_id,
              result.get("name",""), result.get("role",""),
              result.get("overall_score",0),
              result.get("ai_susceptibility_score",0),
              result.get("ai_augment_score",0),
              (result.get("automation_risk") or {}).get("level",""),
              (result.get("automation_risk") or {}).get("timeline",""),
              json.dumps(result), pdf_b64, 1 if paid else 0)

    if DATABASE_URL:
        sql = f"""INSERT INTO reports
            (session_id,user_id,cv_upload_id,name,role,overall_score,
             ai_susceptibility_score,ai_augment_score,automation_risk_level,
             automation_risk_timeline,full_result,pdf_b64,paid)
            VALUES ({','.join([PH]*13)})
            ON CONFLICT(session_id) DO UPDATE SET
            user_id=EXCLUDED.user_id, cv_upload_id=EXCLUDED.cv_upload_id,
            paid=EXCLUDED.paid, pdf_b64=EXCLUDED.pdf_b64,
            full_result=EXCLUDED.full_result RETURNING id"""
        r = _q(sql, params, one=True)
        return r["id"] if r else None
    else:
        sql = f"""INSERT INTO reports
            (session_id,user_id,cv_upload_id,name,role,overall_score,
             ai_susceptibility_score,ai_augment_score,automation_risk_level,
             automation_risk_timeline,full_result,pdf_b64,paid)
            VALUES ({','.join([PH]*13)})
            ON CONFLICT(session_id) DO UPDATE SET
            user_id=excluded.user_id, cv_upload_id=excluded.cv_upload_id,
            paid=excluded.paid, pdf_b64=excluded.pdf_b64,
            full_result=excluded.full_result"""
        with _conn() as c:
            c.execute(sql, params)
            r = c.execute(f"SELECT id FROM reports WHERE session_id={PH}", (session_id,)).fetchone()
            return r[0] if r else None

def get_user_reports(user_id):
    return _q(f"""SELECT id,session_id,name,role,overall_score,
        ai_susceptibility_score,ai_augment_score,
        automation_risk_level,automation_risk_timeline,paid,created_at
        FROM reports WHERE user_id={PH} ORDER BY created_at DESC""",
        (user_id,), many=True)

def get_report_pdf(session_id, user_id):
    return _q(f"SELECT pdf_b64,name FROM reports WHERE session_id={PH} AND user_id={PH} AND paid=1",
              (session_id, user_id), one=True)

def link_items_to_user(session_id, user_id):
    _q(f"UPDATE reports    SET user_id={PH} WHERE session_id={PH} AND user_id IS NULL", (user_id, session_id))
    _q(f"UPDATE cv_uploads SET user_id={PH} WHERE session_id={PH} AND user_id IS NULL", (user_id, session_id))


# ── Roadmap ───────────────────────────────────────────────────────────────────
def save_roadmap_progress(user_id, report_id, skills):
    for skill in skills:
        exists = _q(f"SELECT id FROM roadmap_progress WHERE user_id={PH} AND report_id={PH} AND skill={PH}",
                    (user_id, report_id, skill["skill"]), one=True)
        if not exists:
            _q(f"INSERT INTO roadmap_progress (user_id,report_id,skill,priority,completed) VALUES ({PH},{PH},{PH},{PH},0)",
               (user_id, report_id, skill["skill"], skill.get("priority","medium")))

def toggle_roadmap_item(user_id, item_id, completed):
    _q(f"UPDATE roadmap_progress SET completed={PH}, updated_at={NOW} WHERE id={PH} AND user_id={PH}",
       (1 if completed else 0, item_id, user_id))

def get_roadmap_progress(user_id, report_id):
    return _q(f"""SELECT id,skill,priority,completed,notes,updated_at
        FROM roadmap_progress WHERE user_id={PH} AND report_id={PH}
        ORDER BY CASE priority WHEN 'high' THEN 1 WHEN 'medium' THEN 2 ELSE 3 END""",
        (user_id, report_id), many=True)


# ── Admin helpers ─────────────────────────────────────────────────────────────
def admin_stats():
    return {
        "total_users":      (_q("SELECT COUNT(*) as c FROM users",                    one=True) or {}).get("c", 0),
        "total_cvs":        (_q("SELECT COUNT(*) as c FROM cv_uploads",               one=True) or {}).get("c", 0),
        "total_reports":    (_q("SELECT COUNT(*) as c FROM reports",                  one=True) or {}).get("c", 0),
        "paid_reports":     (_q("SELECT COUNT(*) as c FROM reports WHERE paid=1",     one=True) or {}).get("c", 0),
        "total_storage_mb": (_q("SELECT ROUND(SUM(file_size_kb)/1024.0,2) as s FROM cv_uploads", one=True) or {}).get("s") or 0,
    }

def admin_get_users():
    return _q(f"""SELECT u.id, u.email, u.name, u.created_at, u.last_login,
        COUNT(DISTINCT c.id) as cv_count,
        COUNT(DISTINCT r.id) as report_count,
        SUM(CASE WHEN r.paid=1 THEN 1 ELSE 0 END) as paid_count
        FROM users u
        LEFT JOIN cv_uploads c ON c.user_id=u.id
        LEFT JOIN reports    r ON r.user_id=u.id
        GROUP BY u.id, u.email, u.name, u.created_at, u.last_login
        ORDER BY u.created_at DESC""", many=True)

def admin_get_cvs():
    return _q(f"""SELECT c.id, c.filename, c.file_type, c.file_size_kb,
        c.job_title, c.industry, c.upload_source, c.created_at,
        {SUBSTR}(c.extracted_text,1,300) as text_preview,
        u.email as user_email, u.name as user_name,
        r.overall_score, r.ai_susceptibility_score, r.paid as report_paid
        FROM cv_uploads c
        LEFT JOIN users   u ON u.id=c.user_id
        LEFT JOIN reports r ON r.cv_upload_id=c.id
        ORDER BY c.created_at DESC""", many=True)

def admin_get_reports():
    return _q(f"""SELECT r.id, r.session_id, r.name, r.role,
        r.overall_score, r.ai_susceptibility_score, r.ai_augment_score,
        r.automation_risk_level, r.paid, r.created_at,
        u.email as user_email, u.name as user_name
        FROM reports r LEFT JOIN users u ON u.id=r.user_id
        ORDER BY r.created_at DESC""", many=True)

def admin_get_cv(upload_id):
    return _q(f"SELECT * FROM cv_uploads WHERE id={PH}", (upload_id,), one=True)

def admin_get_report_pdf(session_id):
    return _q(f"SELECT pdf_b64,name FROM reports WHERE session_id={PH} AND paid=1",
              (session_id,), one=True)

def admin_get_all_cvs_for_export():
    return _q(f"""SELECT c.id, c.filename, c.file_type, c.file_b64, c.extracted_text,
        c.created_at, u.email as user_email, u.name as user_name, c.job_title
        FROM cv_uploads c LEFT JOIN users u ON u.id=c.user_id
        ORDER BY c.created_at DESC""", many=True)

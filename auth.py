import os, random, string, bcrypt
from datetime import datetime, timedelta
from flask import Blueprint, request, jsonify
from flask_jwt_extended import create_access_token, jwt_required, get_jwt_identity
from database import get_db
from sendgrid import SendGridAPIClient
from sendgrid.helpers.mail import Mail

auth_bp = Blueprint("auth", __name__)

SENDGRID_API_KEY = os.getenv("SENDGRID_API_KEY", "")
FROM_EMAIL       = os.getenv("FROM_EMAIL", "noreply@workmoat.ai")
OTP_EXPIRY_MINS  = 10


def send_otp_email(to_email, otp, subject="Your WorkMoat.ai code", purpose="sign in"):
    html = f"""
    <div style="font-family:'Helvetica Neue',sans-serif;max-width:480px;margin:0 auto;padding:40px 24px;background:#f9f7f2">
      <div style="background:#fff;border:1px solid #ddd9ce;border-radius:16px;padding:36px;text-align:center">
        <div style="font-size:13px;font-weight:700;letter-spacing:.12em;text-transform:uppercase;color:#1e7f8a;margin-bottom:20px">workmoat.ai</div>
        <div style="font-size:26px;font-weight:700;color:#1a1a18;margin-bottom:8px">Verification code</div>
        <div style="font-size:14px;color:#6b6860;margin-bottom:32px">Use this code to {purpose} on WorkMoat.ai</div>
        <div style="background:#f9f7f2;border:1px solid #ddd9ce;border-radius:12px;padding:24px;margin-bottom:28px">
          <div style="font-size:44px;font-weight:700;letter-spacing:.2em;color:#1e7f8a;font-family:'Courier New',monospace">{otp}</div>
        </div>
        <div style="font-size:12px;color:#9e9b91">Expires in {OTP_EXPIRY_MINS} minutes. If you didn't request this, ignore it.</div>
      </div>
      <div style="text-align:center;margin-top:20px;font-size:11px;color:#9e9b91">workmoat.ai — AI workforce intelligence</div>
    </div>"""
    try:
        sg  = SendGridAPIClient(SENDGRID_API_KEY)
        msg = Mail(from_email=(FROM_EMAIL, "WorkMoat.ai"), to_emails=to_email, subject=subject, html_content=html)
        msg.plain_text_content = f"Your WorkMoat.ai code: {otp}  (expires in {OTP_EXPIRY_MINS} minutes)"
        r = sg.send(msg)
        return r.status_code in (200, 202)
    except Exception as e:
        print(f"Email error: {e}")
        return False


def hash_pw(password):
    return bcrypt.hashpw(password.encode(), bcrypt.gensalt()).decode()


def check_pw(password, hashed):
    try:
        return bcrypt.checkpw(password.encode(), hashed.encode())
    except Exception:
        return False


def store_otp(email):
    otp     = "".join(random.choices(string.digits, k=6))
    expires = (datetime.utcnow() + timedelta(minutes=OTP_EXPIRY_MINS)).isoformat()
    conn    = get_db()
    conn.execute("UPDATE otp_codes SET used=1 WHERE email=?", (email,))
    conn.execute("INSERT INTO otp_codes (email,code,expires_at) VALUES (?,?,?)", (email, otp, expires))
    conn.commit(); conn.close()
    return otp


def use_otp(email, code):
    conn = get_db()
    row  = conn.execute(
        "SELECT id,code,expires_at FROM otp_codes WHERE email=? AND used=0 ORDER BY created_at DESC LIMIT 1",
        (email,)
    ).fetchone()
    conn.close()
    if not row:                 return False, "No active code found. Please request a new one."
    if row["code"] != code:     return False, "Incorrect code. Please try again."
    if datetime.utcnow() > datetime.fromisoformat(row["expires_at"]):
        return False, "Code expired. Please request a new one."
    conn = get_db()
    conn.execute("UPDATE otp_codes SET used=1 WHERE id=?", (row["id"],))
    conn.commit(); conn.close()
    return True, "ok"


def upsert_user(email, name="", pw_hash=""):
    conn = get_db()
    existing = conn.execute("SELECT id,name FROM users WHERE email=?", (email,)).fetchone()
    user_name = name or (existing["name"] if existing else None) or email.split("@")[0]
    if existing:
        uid = existing["id"]
        if pw_hash:
            conn.execute("UPDATE users SET name=?,password_hash=?,last_login=datetime('now') WHERE id=?", (user_name, pw_hash, uid))
        else:
            conn.execute("UPDATE users SET name=?,last_login=datetime('now') WHERE id=?", (user_name, uid))
    else:
        conn.execute("INSERT INTO users (email,name,password_hash,last_login) VALUES (?,?,?,datetime('now'))", (email, user_name, pw_hash))
        uid = conn.execute("SELECT last_insert_rowid()").fetchone()[0]
    conn.commit(); conn.close()
    return uid, user_name


def make_token(uid, email, name):
    return create_access_token(identity=str(uid), additional_claims={"email": email, "name": name})


# ── Sign up ───────────────────────────────────────────────────────────────────
@auth_bp.route("/api/auth/signup", methods=["POST"])
def signup():
    d        = request.get_json()
    email    = (d.get("email") or "").strip().lower()
    name     = (d.get("name") or "").strip()
    password = (d.get("password") or "").strip()

    if not email or "@" not in email: return jsonify({"error": "Valid email required"}), 400
    if not name:                      return jsonify({"error": "Name is required"}), 400
    if len(password) < 6:             return jsonify({"error": "Password must be at least 6 characters"}), 400

    conn = get_db()
    existing = conn.execute("SELECT id,password_hash FROM users WHERE email=?", (email,)).fetchone()
    conn.close()
    if existing and existing["password_hash"]:
        return jsonify({"error": "Email already registered. Please sign in."}), 409

    uid, uname = upsert_user(email, name, hash_pw(password))
    return jsonify({"success": True, "token": make_token(uid, email, uname), "user": {"id": uid, "email": email, "name": uname}})


# ── Sign in ───────────────────────────────────────────────────────────────────
@auth_bp.route("/api/auth/login", methods=["POST"])
def login():
    d        = request.get_json()
    email    = (d.get("email") or "").strip().lower()
    password = (d.get("password") or "").strip()

    if not email or not password: return jsonify({"error": "Email and password required"}), 400

    conn = get_db()
    user = conn.execute("SELECT id,name,password_hash FROM users WHERE email=?", (email,)).fetchone()
    conn.close()

    if not user:               return jsonify({"error": "No account found. Please sign up first."}), 404
    if not user["password_hash"]: return jsonify({"error": "Use 'Forgot password' to set up a password for this account."}), 400
    if not check_pw(password, user["password_hash"]): return jsonify({"error": "Incorrect password. Please try again."}), 401

    conn = get_db()
    conn.execute("UPDATE users SET last_login=datetime('now') WHERE id=?", (user["id"],))
    conn.commit(); conn.close()

    return jsonify({"success": True, "token": make_token(user["id"], email, user["name"]), "user": {"id": user["id"], "email": email, "name": user["name"]}})


# ── Forgot password — send OTP ────────────────────────────────────────────────
@auth_bp.route("/api/auth/send-otp", methods=["POST"])
def send_otp():
    d     = request.get_json()
    email = (d.get("email") or "").strip().lower()
    if not email or "@" not in email: return jsonify({"error": "Valid email required"}), 400

    otp  = store_otp(email)
    sent = send_otp_email(email, otp, subject="Reset your WorkMoat.ai password", purpose="reset your password")
    resp = {"success": True, "message": f"Reset code sent to {email}"}
    if not sent:
        resp["otp_fallback"] = otp
        resp["warning"] = "Email delivery unavailable — code shown for testing"
    return jsonify(resp)


# ── Reset password — verify OTP + set new password ───────────────────────────
@auth_bp.route("/api/auth/reset-password", methods=["POST"])
def reset_password():
    d            = request.get_json()
    email        = (d.get("email") or "").strip().lower()
    code         = (d.get("code") or "").strip()
    new_password = (d.get("new_password") or "").strip()

    if not email or not code or not new_password: return jsonify({"error": "Email, code and new password required"}), 400
    if len(new_password) < 6: return jsonify({"error": "Password must be at least 6 characters"}), 400

    ok, msg = use_otp(email, code)
    if not ok: return jsonify({"error": msg}), 400

    uid, uname = upsert_user(email, "", hash_pw(new_password))
    return jsonify({"success": True, "token": make_token(uid, email, uname), "user": {"id": uid, "email": email, "name": uname}})


# ── Me ────────────────────────────────────────────────────────────────────────
@auth_bp.route("/api/auth/me", methods=["GET"])
@jwt_required()
def me():
    uid  = int(get_jwt_identity())
    conn = get_db()
    user = conn.execute("SELECT id,email,name,created_at FROM users WHERE id=?", (uid,)).fetchone()
    conn.close()
    if not user: return jsonify({"error": "User not found"}), 404
    return jsonify(dict(user))

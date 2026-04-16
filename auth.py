import os, random, string, bcrypt
from datetime import datetime, timedelta
from flask import Blueprint, request, jsonify
from flask_jwt_extended import create_access_token, jwt_required, get_jwt_identity
from database import (get_user_by_email, get_user_by_id, create_user, update_user,
                      store_otp_db, get_latest_otp, mark_otp_used)
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
        <div style="font-size:12px;color:#9e9b91">Expires in {OTP_EXPIRY_MINS} minutes.</div>
      </div>
    </div>"""
    try:
        sg  = SendGridAPIClient(SENDGRID_API_KEY)
        msg = Mail(from_email=(FROM_EMAIL, "WorkMoat.ai"), to_emails=to_email,
                   subject=subject, html_content=html)
        msg.plain_text_content = f"Your WorkMoat.ai code: {otp} (expires in {OTP_EXPIRY_MINS} mins)"
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


def make_token(uid, email, name):
    return create_access_token(
        identity=str(uid),
        additional_claims={"email": email, "name": name}
    )


def upsert_user(email, name="", pw_hash=""):
    existing = get_user_by_email(email)
    user_name = name or (existing["name"] if existing else None) or email.split("@")[0]
    if existing:
        update_user(existing["id"], name=user_name, pw_hash=pw_hash if pw_hash else None)
        return existing["id"], user_name
    else:
        uid = create_user(email, user_name, pw_hash)
        return uid, user_name


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

    existing = get_user_by_email(email)
    if existing and existing.get("password_hash"):
        return jsonify({"error": "Email already registered. Please sign in."}), 409

    uid, uname = upsert_user(email, name, hash_pw(password))
    return jsonify({"success": True, "token": make_token(uid, email, uname),
                    "user": {"id": uid, "email": email, "name": uname}})


# ── Sign in ───────────────────────────────────────────────────────────────────
@auth_bp.route("/api/auth/login", methods=["POST"])
def login():
    d        = request.get_json()
    email    = (d.get("email") or "").strip().lower()
    password = (d.get("password") or "").strip()

    if not email or not password: return jsonify({"error": "Email and password required"}), 400

    user = get_user_by_email(email)
    if not user:
        return jsonify({"error": "No account found. Please sign up first."}), 404
    if not user.get("password_hash"):
        return jsonify({"error": "Use 'Forgot password' to set up a password for this account."}), 400
    if not check_pw(password, user["password_hash"]):
        return jsonify({"error": "Incorrect password. Please try again."}), 401

    update_user(user["id"], name=user["name"])
    return jsonify({"success": True,
                    "token": make_token(user["id"], email, user["name"]),
                    "user": {"id": user["id"], "email": email, "name": user["name"]}})


# ── Send reset OTP ────────────────────────────────────────────────────────────
@auth_bp.route("/api/auth/send-otp", methods=["POST"])
def send_otp():
    d     = request.get_json()
    email = (d.get("email") or "").strip().lower()
    if not email or "@" not in email:
        return jsonify({"error": "Valid email required"}), 400

    otp     = "".join(random.choices(string.digits, k=6))
    expires = (datetime.utcnow() + timedelta(minutes=OTP_EXPIRY_MINS)).isoformat()
    store_otp_db(email, otp, expires)

    sent = send_otp_email(email, otp, subject="Reset your WorkMoat.ai password",
                          purpose="reset your password")
    resp = {"success": True, "message": f"Reset code sent to {email}"}
    if not sent:
        resp["otp_fallback"] = otp
        resp["warning"] = "Email delivery unavailable — code shown for testing"
    return jsonify(resp)


# ── Reset password ────────────────────────────────────────────────────────────
@auth_bp.route("/api/auth/reset-password", methods=["POST"])
def reset_password():
    d            = request.get_json()
    email        = (d.get("email") or "").strip().lower()
    code         = (d.get("code") or "").strip()
    new_password = (d.get("new_password") or "").strip()

    if not email or not code or not new_password:
        return jsonify({"error": "Email, code and new password required"}), 400
    if len(new_password) < 6:
        return jsonify({"error": "Password must be at least 6 characters"}), 400

    row = get_latest_otp(email)
    if not row:             return jsonify({"error": "No active code. Please request a new one."}), 400
    if row["code"] != code: return jsonify({"error": "Incorrect code. Please try again."}), 400
    if datetime.utcnow() > datetime.fromisoformat(str(row["expires_at"]).replace("Z","")):
        return jsonify({"error": "Code expired. Please request a new one."}), 400

    mark_otp_used(row["id"])
    uid, uname = upsert_user(email, "", hash_pw(new_password))
    return jsonify({"success": True, "token": make_token(uid, email, uname),
                    "user": {"id": uid, "email": email, "name": uname}})


# ── Me ────────────────────────────────────────────────────────────────────────
@auth_bp.route("/api/auth/me", methods=["GET"])
@jwt_required()
def me():
    uid  = int(get_jwt_identity())
    user = get_user_by_id(uid)
    if not user: return jsonify({"error": "User not found"}), 404
    return jsonify(user)

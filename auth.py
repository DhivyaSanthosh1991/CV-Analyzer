import os, random, string
from datetime import datetime, timedelta
from flask import Blueprint, request, jsonify
from flask_jwt_extended import create_access_token, jwt_required, get_jwt_identity
from database import get_db, init_db
from sendgrid import SendGridAPIClient
from sendgrid.helpers.mail import Mail

auth_bp = Blueprint("auth", __name__)

SENDGRID_API_KEY = os.getenv("SENDGRID_API_KEY", "")
FROM_EMAIL       = os.getenv("FROM_EMAIL", "noreply@workmoat.ai")
OTP_EXPIRY_MINS  = 10


def send_otp_email(to_email: str, otp: str, name: str = "") -> bool:
    greeting = f"Hi {name.split()[0]}," if name else "Hi,"
    html = f"""
    <div style="font-family:'Helvetica Neue',sans-serif;max-width:480px;margin:0 auto;padding:40px 24px;background:#f9f7f2">
      <div style="background:#fff;border:1px solid #ddd9ce;border-radius:16px;padding:36px;text-align:center">
        <div style="font-size:13px;font-weight:700;letter-spacing:.12em;text-transform:uppercase;color:#1e7f8a;margin-bottom:20px">workmoat.ai</div>
        <div style="font-size:28px;font-weight:700;letter-spacing:-.02em;color:#1a1a18;margin-bottom:8px">Your sign-in code</div>
        <div style="font-size:14px;color:#6b6860;margin-bottom:32px">{greeting} Use this code to sign in to WorkMoat.</div>
        <div style="background:#f9f7f2;border:1px solid #ddd9ce;border-radius:12px;padding:24px;margin-bottom:28px">
          <div style="font-size:44px;font-weight:700;letter-spacing:.2em;color:#1e7f8a;font-family:'Courier New',monospace">{otp}</div>
        </div>
        <div style="font-size:12px;color:#9e9b91">This code expires in {OTP_EXPIRY_MINS} minutes.<br>If you didn't request this, you can safely ignore it.</div>
      </div>
      <div style="text-align:center;margin-top:20px;font-size:11px;color:#9e9b91">workmoat.ai — AI workforce intelligence</div>
    </div>"""

    try:
        sg = SendGridAPIClient(SENDGRID_API_KEY)
        msg = Mail(
            from_email=(FROM_EMAIL, "WorkMoat"),
            to_emails=to_email,
            subject="Your WorkMoat sign-in code",
            html_content=html
        )
        msg.plain_text_content = f"Your WorkMoat sign-in code is: {otp}\n\nExpires in {OTP_EXPIRY_MINS} minutes."
        r = sg.send(msg)
        return r.status_code in (200, 202)
    except Exception as e:
        print(f"OTP email error: {e}")
        return False


@auth_bp.route("/api/auth/send-otp", methods=["POST"])
def send_otp():
    data  = request.get_json()
    email = (data.get("email") or "").strip().lower()
    if not email or "@" not in email:
        return jsonify({"error": "Valid email required"}), 400

    # Generate 6-digit OTP
    otp      = "".join(random.choices(string.digits, k=6))
    expires  = (datetime.utcnow() + timedelta(minutes=OTP_EXPIRY_MINS)).isoformat()

    conn = get_db()
    # Invalidate previous OTPs for this email
    conn.execute("UPDATE otp_codes SET used=1 WHERE email=?", (email,))
    conn.execute(
        "INSERT INTO otp_codes (email, code, expires_at) VALUES (?,?,?)",
        (email, otp, expires)
    )
    conn.commit()
    conn.close()

    # Try sending email — in dev, also return OTP in response for testing
    sent = send_otp_email(to_email=email, otp=otp)

    resp = {"success": True, "message": f"Code sent to {email}"}
    if not sent:
        # Fallback: include OTP in response if email fails (remove in production)
        resp["otp_fallback"] = otp
        resp["warning"] = "Email delivery failed — use the code above to test"

    return jsonify(resp)


@auth_bp.route("/api/auth/verify-otp", methods=["POST"])
def verify_otp():
    data  = request.get_json()
    email = (data.get("email") or "").strip().lower()
    code  = (data.get("code") or "").strip()
    name  = (data.get("name") or "").strip()

    if not email or not code:
        return jsonify({"error": "Email and code required"}), 400

    conn = get_db()
    row = conn.execute("""
        SELECT id, code, expires_at FROM otp_codes
        WHERE email=? AND used=0
        ORDER BY created_at DESC LIMIT 1
    """, (email,)).fetchone()

    if not row:
        conn.close()
        return jsonify({"error": "No active code found. Please request a new one."}), 400

    if row["code"] != code:
        conn.close()
        return jsonify({"error": "Incorrect code. Please try again."}), 400

    if datetime.utcnow() > datetime.fromisoformat(row["expires_at"]):
        conn.close()
        return jsonify({"error": "Code expired. Please request a new one."}), 400

    # Mark OTP as used
    conn.execute("UPDATE otp_codes SET used=1 WHERE id=?", (row["id"],))

    # Upsert user
    existing = conn.execute("SELECT id, name FROM users WHERE email=?", (email,)).fetchone()
    if existing:
        user_id   = existing["id"]
        user_name = name or existing["name"] or email.split("@")[0]
        conn.execute("UPDATE users SET last_login=datetime('now'), name=? WHERE id=?", (user_name, user_id))
    else:
        user_name = name or email.split("@")[0]
        conn.execute(
            "INSERT INTO users (email, name, last_login) VALUES (?,?,datetime('now'))",
            (email, user_name)
        )
        user_id = conn.execute("SELECT last_insert_rowid()").fetchone()[0]

    conn.commit()
    conn.close()

    token = create_access_token(identity=str(user_id), additional_claims={"email": email, "name": user_name})
    return jsonify({
        "success": True,
        "token":   token,
        "user":    {"id": user_id, "email": email, "name": user_name}
    })


@auth_bp.route("/api/auth/me", methods=["GET"])
@jwt_required()
def me():
    user_id = int(get_jwt_identity())
    conn = get_db()
    user = conn.execute("SELECT id, email, name, created_at FROM users WHERE id=?", (user_id,)).fetchone()
    conn.close()
    if not user:
        return jsonify({"error": "User not found"}), 404
    return jsonify(dict(user))

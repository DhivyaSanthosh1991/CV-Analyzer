import os, json, hmac, hashlib, uuid, re, io, base64
from flask import Flask, request, jsonify, send_file, render_template
from flask_cors import CORS
from flask_jwt_extended import JWTManager, jwt_required, get_jwt_identity, verify_jwt_in_request
import anthropic
import razorpay
from pdf_generator import generate_report_pdf
from email_sender import send_report_email
from database import (init_db, migrate_db,
                       save_report, get_user_reports, get_report_pdf,
                       save_roadmap_progress, toggle_roadmap_item, get_roadmap_progress,
                       save_cv_upload, save_cv_text, get_user_cv_uploads,
                       get_cv_upload, delete_cv_upload, get_cv_storage_stats,
                       link_items_to_user, _conn as get_db_ctx)
from auth import auth_bp
from admin import admin_bp

app = Flask(__name__)
CORS(app)

# ── Config ────────────────────────────────────────────────────────────────────
ANTHROPIC_API_KEY   = os.getenv("ANTHROPIC_API_KEY",  "YOUR_ANTHROPIC_KEY")
RAZORPAY_KEY_ID     = os.getenv("RAZORPAY_KEY_ID",    "YOUR_RAZORPAY_KEY_ID")
RAZORPAY_KEY_SECRET = os.getenv("RAZORPAY_KEY_SECRET", "YOUR_RAZORPAY_SECRET")
SENDGRID_API_KEY    = os.getenv("SENDGRID_API_KEY",    "YOUR_SENDGRID_API_KEY")
JWT_SECRET          = os.getenv("JWT_SECRET_KEY",      "workmoat-dev-secret-change-in-prod")
ADMIN_SECRET        = os.getenv("ADMIN_SECRET_KEY",   "workmoat-admin-change-this")
REPORT_PRICE_PAISE  = 19900

app.config["JWT_SECRET_KEY"]       = JWT_SECRET
app.config["JWT_ACCESS_TOKEN_EXPIRES"] = False  # no expiry — user stays logged in

jwt_manager = JWTManager(app)
app.register_blueprint(auth_bp)
app.register_blueprint(admin_bp)

anthropic_client = anthropic.Anthropic(api_key=ANTHROPIC_API_KEY)
razorpay_client  = razorpay.Client(auth=(RAZORPAY_KEY_ID, RAZORPAY_KEY_SECRET))

sessions: dict = {}

# Init DB on startup
with app.app_context():
    init_db()
    migrate_db()

# ── System prompt ─────────────────────────────────────────────────────────────
SYSTEM_PROMPT = """You are an expert CV analyst and AI workforce advisor. Analyse the CV and return ONLY valid JSON — no markdown, no backticks, no preamble.

Return exactly this structure:
{
  "name": "<detected name or 'Professional'>",
  "role": "<detected current/target role>",
  "overall_score": <0-100>,
  "ai_susceptibility_score": <0-100, higher = more at risk>,
  "ai_augment_score": <0-100, higher = more augmentable by AI tools>,
  "cv_sections": {
    "contact_info": {"score":<0-100>,"feedback":"<1 sentence>","status":"good|warn|info"},
    "summary":      {"score":<0-100>,"feedback":"<1 sentence>","status":"good|warn|info"},
    "experience":   {"score":<0-100>,"feedback":"<1 sentence>","status":"good|warn|info"},
    "skills":       {"score":<0-100>,"feedback":"<1 sentence>","status":"good|warn|info"},
    "formatting":   {"score":<0-100>,"feedback":"<1 sentence>","status":"good|warn|info"}
  },
  "role_breakdown": {
    "automatable_tasks": ["task1","task2","task3"],
    "human_tasks": ["task1","task2","task3"],
    "automation_pct": <0-100>
  },
  "automation_risk": {
    "level": "low|medium|high",
    "summary": "<2 sentences>",
    "timeline": "<e.g. 3-5 years>"
  },
  "ai_systems": {
    "already_replacing": ["tool1","tool2","tool3"],
    "augmenting": ["tool1","tool2","tool3"]
  },
  "job_fit": {
    "score": <0-100 or null>,
    "matched_skills": ["s1","s2","s3"],
    "missing_skills": ["s1","s2","s3"]
  },
  "strategic_position": "<3 sentences about their unique career moat and how to defend it>",
  "upskilling_roadmap": [
    {"priority":"high",  "skill":"<skill name>","reason":"<why this protects them>","resources":"<course/platform>"},
    {"priority":"high",  "skill":"<skill name>","reason":"<why>","resources":"<where>"},
    {"priority":"medium","skill":"<skill name>","reason":"<why>","resources":"<where>"},
    {"priority":"medium","skill":"<skill name>","reason":"<why>","resources":"<where>"},
    {"priority":"low",   "skill":"<skill name>","reason":"<why>","resources":"<where>"}
  ],
  "top_improvements": [
    {"priority":"high",  "suggestion":"<concrete CV fix>"},
    {"priority":"high",  "suggestion":"<concrete CV fix>"},
    {"priority":"medium","suggestion":"<concrete CV fix>"},
    {"priority":"low",   "suggestion":"<concrete CV fix>"}
  ],
  "strengths": ["s1","s2","s3","s4"]
}"""

# ── Helper: get optional current user ────────────────────────────────────────
def get_current_user_id():
    try:
        verify_jwt_in_request(optional=True)
        uid = get_jwt_identity()
        return int(uid) if uid else None
    except Exception:
        return None

# ── File extraction ───────────────────────────────────────────────────────────
def extract_text_from_file(file_bytes: bytes, filename: str) -> str:
    fname = filename.lower()
    if fname.endswith(".pdf"):
        try:
            import pdfplumber
            parts = []
            with pdfplumber.open(io.BytesIO(file_bytes)) as pdf:
                for page in pdf.pages:
                    t = page.extract_text()
                    if t: parts.append(t)
            return "\n\n".join(parts)
        except Exception as e:
            return f"[PDF extraction error: {e}]"
    elif fname.endswith(".docx"):
        try:
            from docx import Document
            doc = Document(io.BytesIO(file_bytes))
            return "\n".join(p.text for p in doc.paragraphs if p.text.strip())
        except Exception as e:
            return f"[DOCX extraction error: {e}]"
    else:
        try:    return file_bytes.decode("utf-8")
        except: return file_bytes.decode("latin-1", errors="replace")

# ── Routes ────────────────────────────────────────────────────────────────────
@app.route("/")
def index():
    return render_template("index.html", razorpay_key=RAZORPAY_KEY_ID)

@app.route("/api/extract-text", methods=["POST"])
def extract_text():
    if "file" not in request.files:
        return jsonify({"error": "No file provided"}), 400
    f = request.files["file"]
    if not f.filename:
        return jsonify({"error": "Empty filename"}), 400

    file_bytes = f.read()
    text = extract_text_from_file(file_bytes, f.filename)
    if not text or len(text.strip()) < 20:
        return jsonify({"error": "Could not extract text from file"}), 422

    # Save file to CV storage for logged-in users
    session_id = request.form.get("session_id") or str(uuid.uuid4())
    job_title  = request.form.get("job_title", "")
    industry   = request.form.get("industry", "")
    user_id    = get_current_user_id()

    cv_upload_id = None
    if user_id:
        cv_upload_id = save_cv_upload(
            session_id=session_id,
            file_bytes=file_bytes,
            filename=f.filename,
            extracted_text=text,
            job_title=job_title,
            industry=industry,
            user_id=user_id
        )

    return jsonify({
        "text":          text[:6000],
        "session_id":    session_id,
        "cv_upload_id":  cv_upload_id
    })

@app.route("/api/analyse", methods=["POST"])
def analyse():
    data         = request.get_json()
    cv_text      = (data.get("cv_text") or "").strip()
    job_title    = (data.get("job_title") or "").strip()
    industry     = (data.get("industry") or "").strip()
    cv_upload_id = data.get("cv_upload_id")   # passed from frontend if file was uploaded

    if len(cv_text) < 60:
        return jsonify({"error": "CV text too short"}), 400

    user_msg = f"CV:\n{cv_text[:4000]}"
    if job_title: user_msg += f"\n\nTarget role: {job_title}"
    if industry:  user_msg += f"\nIndustry: {industry}"

    try:
        message = anthropic_client.messages.create(
            model="claude-sonnet-4-20250514", max_tokens=1500,
            system=SYSTEM_PROMPT,
            messages=[{"role": "user", "content": user_msg}]
        )
        raw    = message.content[0].text
        result = json.loads(re.sub(r"```json|```", "", raw).strip())
    except Exception as e:
        return jsonify({"error": str(e)}), 500

    session_id = str(uuid.uuid4())
    sessions[session_id] = {"result": result, "paid": False}

    user_id = get_current_user_id()

    # If CV was pasted (no file upload), save the text now
    if user_id and not cv_upload_id:
        cv_upload_id = save_cv_text(
            session_id=session_id,
            extracted_text=cv_text,
            job_title=job_title,
            industry=industry,
            user_id=user_id
        )

    # Save report linked to cv_upload
    save_report(session_id, result, paid=False,
                user_id=user_id, cv_upload_id=cv_upload_id)

    preview = {k: result[k] for k in [
        "name", "role", "overall_score", "ai_susceptibility_score",
        "ai_augment_score", "cv_sections", "role_breakdown",
        "automation_risk", "job_fit", "strengths"
    ] if k in result}

    return jsonify({"session_id": session_id, "preview": preview})

@app.route("/api/create-order", methods=["POST"])
def create_order():
    data       = request.get_json()
    session_id = data.get("session_id")
    email      = (data.get("email") or "").strip().lower()
    if not session_id or session_id not in sessions:
        return jsonify({"error": "Invalid session"}), 400
    if not email or "@" not in email:
        return jsonify({"error": "Valid email required"}), 400
    sessions[session_id]["email"] = email
    try:
        order = razorpay_client.order.create({
            "amount": REPORT_PRICE_PAISE, "currency": "INR",
            "receipt": f"wm_{session_id[:8]}",
            "notes":   {"session_id": session_id, "email": email}
        })
        sessions[session_id]["order_id"] = order["id"]
        return jsonify({"order_id": order["id"], "amount": REPORT_PRICE_PAISE,
                        "currency": "INR", "key": RAZORPAY_KEY_ID})
    except Exception as e:
        return jsonify({"error": str(e)}), 500

@app.route("/api/verify-payment", methods=["POST"])
def verify_payment():
    data       = request.get_json()
    session_id = data.get("session_id")
    payment_id = data.get("razorpay_payment_id")
    order_id   = data.get("razorpay_order_id")
    signature  = data.get("razorpay_signature")
    if not all([session_id, payment_id, order_id, signature]):
        return jsonify({"error": "Missing payment data"}), 400

    body         = f"{order_id}|{payment_id}"
    expected_sig = hmac.new(RAZORPAY_KEY_SECRET.encode(), body.encode(), hashlib.sha256).hexdigest()
    if not hmac.compare_digest(expected_sig, signature):
        return jsonify({"error": "Payment verification failed"}), 400

    session = sessions.get(session_id)
    if not session:
        return jsonify({"error": "Session not found"}), 404

    session["paid"] = True
    full_result = session["result"]

    # Generate PDF
    reports_dir = os.path.join(os.path.dirname(__file__), "reports")
    os.makedirs(reports_dir, exist_ok=True)
    pdf_path = os.path.join(reports_dir, f"{session_id}.pdf")
    generate_report_pdf(full_result, pdf_path)
    session["pdf_path"] = pdf_path

    pdf_b64 = ""
    try:
        with open(pdf_path, "rb") as f:
            pdf_b64 = base64.b64encode(f.read()).decode("utf-8")
    except Exception:
        pass

    # Send email
    email      = session.get("email","")
    name       = full_result.get("name","Professional")
    role       = full_result.get("role","–")
    email_sent = False
    if email:
        ok, _ = send_report_email(email, name, role, full_result, pdf_path)
        email_sent = ok

    # Save paid report & link to user
    user_id    = get_current_user_id()
    report_id  = save_report(session_id, full_result, paid=True, pdf_b64=pdf_b64, user_id=user_id)

    # Auto-create roadmap progress items
    roadmap = full_result.get("upskilling_roadmap", [])
    if user_id and report_id and roadmap:
        save_roadmap_progress(user_id, report_id, roadmap)

    paid_sections = {k: full_result[k] for k in [
        "strategic_position","upskilling_roadmap","top_improvements","ai_systems"
    ] if k in full_result}

    return jsonify({
        "success":       True,
        "paid_sections": paid_sections,
        "download_url":  f"/api/download/{session_id}",
        "pdf_b64":       pdf_b64,
        "pdf_name":      f"WorkMoat_Report_{name.replace(' ','_')}.pdf",
        "email_sent":    email_sent,
        "email":         email,
        "report_id":     report_id
    })

@app.route("/api/download/<session_id>")
def download_report(session_id):
    session = sessions.get(session_id)
    if not session or not session.get("paid"):
        return jsonify({"error": "Unauthorized"}), 403
    pdf_path = session.get("pdf_path")
    if not pdf_path or not os.path.exists(pdf_path):
        return jsonify({"error": "Report not found"}), 404
    name = session["result"].get("name","report").replace(" ","_")
    return send_file(pdf_path, as_attachment=True,
                     download_name=f"WorkMoat_Report_{name}.pdf",
                     mimetype="application/pdf")

# ── User dashboard API ────────────────────────────────────────────────────────
@app.route("/api/user/reports", methods=["GET"])
@jwt_required()
def user_reports():
    user_id = int(get_jwt_identity())
    return jsonify(get_user_reports(user_id))

@app.route("/api/user/report/<session_id>/pdf", methods=["GET"])
@jwt_required()
def user_report_pdf(session_id):
    user_id = int(get_jwt_identity())
    row = get_report_pdf(session_id, user_id)
    if not row:
        return jsonify({"error": "Report not found or not paid"}), 404
    return jsonify({"pdf_b64": row["pdf_b64"], "name": row["name"]})

@app.route("/api/user/roadmap/<int:report_id>", methods=["GET"])
@jwt_required()
def user_roadmap(report_id):
    user_id = int(get_jwt_identity())
    items   = get_roadmap_progress(user_id, report_id)
    return jsonify(items)

@app.route("/api/user/roadmap/<int:item_id>/toggle", methods=["POST"])
@jwt_required()
def toggle_roadmap(item_id):
    user_id   = int(get_jwt_identity())
    completed = request.get_json().get("completed", False)
    toggle_roadmap_item(user_id, item_id, completed)
    return jsonify({"success": True})

@app.route("/api/user/link-report", methods=["POST"])
@jwt_required()
def link_report():
    """Link anonymous session report + CV upload to the logged-in user."""
    user_id    = int(get_jwt_identity())
    session_id = request.get_json().get("session_id")
    if not session_id: return jsonify({"error": "Missing session_id"}), 400
    link_items_to_user(session_id, user_id)
    return jsonify({"success": True})


# ── CV Storage API ────────────────────────────────────────────────────────────

@app.route("/api/user/cvs", methods=["GET"])
@jwt_required()
def list_cvs():
    user_id = int(get_jwt_identity())
    uploads = get_user_cv_uploads(user_id)
    stats   = get_cv_storage_stats(user_id)
    return jsonify({"uploads": uploads, "stats": stats})


@app.route("/api/user/cvs/<int:upload_id>", methods=["GET"])
@jwt_required()
def get_cv(upload_id):
    user_id = int(get_jwt_identity())
    cv = get_cv_upload(upload_id, user_id)
    if not cv:
        return jsonify({"error": "CV not found"}), 404
    return jsonify(cv)


@app.route("/api/user/cvs/<int:upload_id>/download", methods=["GET"])
@jwt_required()
def download_cv(upload_id):
    user_id = int(get_jwt_identity())
    cv = get_cv_upload(upload_id, user_id)
    if not cv:
        return jsonify({"error": "CV not found"}), 404
    if not cv.get("file_b64"):
        return jsonify({"error": "No file stored for this CV"}), 404

    file_bytes = base64.b64decode(cv["file_b64"])
    ext        = cv.get("file_type", "txt")
    mime_map   = {"pdf": "application/pdf",
                  "docx": "application/vnd.openxmlformats-officedocument.wordprocessingml.document",
                  "txt": "text/plain"}
    mime = mime_map.get(ext, "application/octet-stream")
    filename = cv.get("filename") or f"cv_{upload_id}.{ext}"

    return send_file(
        io.BytesIO(file_bytes),
        as_attachment=True,
        download_name=filename,
        mimetype=mime
    )


@app.route("/api/user/cvs/<int:upload_id>", methods=["DELETE"])
@jwt_required()
def delete_cv(upload_id):
    user_id = int(get_jwt_identity())
    deleted = delete_cv_upload(upload_id, user_id)
    if not deleted:
        return jsonify({"error": "CV not found or already deleted"}), 404
    return jsonify({"success": True})


if __name__ == "__main__":
    app.run(debug=True, port=5000)

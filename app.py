import os, json, hmac, hashlib, uuid, re, io, base64
from flask import Flask, request, jsonify, send_file, render_template
from flask_cors import CORS
import anthropic
import razorpay
from pdf_generator import generate_report_pdf
from email_sender import send_report_email

app = Flask(__name__)
CORS(app)

# ── Config (replace with real keys in production) ────────────────────────────
ANTHROPIC_API_KEY   = os.getenv("ANTHROPIC_API_KEY",  "YOUR_ANTHROPIC_KEY")
RAZORPAY_KEY_ID     = os.getenv("RAZORPAY_KEY_ID",    "YOUR_RAZORPAY_KEY_ID")
RAZORPAY_KEY_SECRET = os.getenv("RAZORPAY_KEY_SECRET", "YOUR_RAZORPAY_SECRET")
SENDGRID_API_KEY    = os.getenv("SENDGRID_API_KEY",    "YOUR_SENDGRID_API_KEY")
REPORT_PRICE_PAISE  = 19900   # ₹199 in paise

anthropic_client = anthropic.Anthropic(api_key=ANTHROPIC_API_KEY)
razorpay_client  = razorpay.Client(auth=(RAZORPAY_KEY_ID, RAZORPAY_KEY_SECRET))

# In-memory session store (use Redis/DB in production)
sessions: dict = {}

# ── Prompts ───────────────────────────────────────────────────────────────────
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

# ── Routes ────────────────────────────────────────────────────────────────────

def extract_text_from_file(file_bytes: bytes, filename: str) -> str:
    """Extract plain text from PDF, DOCX, or TXT file bytes."""
    fname = filename.lower()

    if fname.endswith(".pdf"):
        try:
            import pdfplumber
            text_parts = []
            with pdfplumber.open(io.BytesIO(file_bytes)) as pdf:
                for page in pdf.pages:
                    t = page.extract_text()
                    if t:
                        text_parts.append(t)
            return "\n\n".join(text_parts)
        except Exception as e:
            return f"[PDF extraction error: {e}]"

    elif fname.endswith(".docx"):
        try:
            from docx import Document
            doc = Document(io.BytesIO(file_bytes))
            paras = [p.text for p in doc.paragraphs if p.text.strip()]
            return "\n".join(paras)
        except Exception as e:
            return f"[DOCX extraction error: {e}]"

    else:
        # Plain text — try UTF-8, fall back to latin-1
        try:
            return file_bytes.decode("utf-8")
        except UnicodeDecodeError:
            return file_bytes.decode("latin-1", errors="replace")


@app.route("/api/extract-text", methods=["POST"])
def extract_text():
    """Accept a file upload and return extracted plain text."""
    if "file" not in request.files:
        return jsonify({"error": "No file provided"}), 400
    f = request.files["file"]
    if not f.filename:
        return jsonify({"error": "Empty filename"}), 400
    file_bytes = f.read()
    text = extract_text_from_file(file_bytes, f.filename)
    if not text or len(text.strip()) < 20:
        return jsonify({"error": "Could not extract text from file"}), 422
    return jsonify({"text": text[:6000]})


@app.route("/")
def index():
    return render_template("index.html", razorpay_key=RAZORPAY_KEY_ID)


@app.route("/api/analyse", methods=["POST"])
def analyse():
    data = request.get_json()
    cv_text   = (data.get("cv_text") or "").strip()
    job_title = (data.get("job_title") or "").strip()
    industry  = (data.get("industry") or "").strip()

    if len(cv_text) < 60:
        return jsonify({"error": "CV text too short"}), 400

    user_msg = f"CV:\n{cv_text[:4000]}"
    if job_title: user_msg += f"\n\nTarget role: {job_title}"
    if industry:  user_msg += f"\nIndustry: {industry}"

    try:
        message = anthropic_client.messages.create(
            model="claude-sonnet-4-20250514",
            max_tokens=1500,
            system=SYSTEM_PROMPT,
            messages=[{"role": "user", "content": user_msg}]
        )
        raw = message.content[0].text
        clean = re.sub(r"```json|```", "", raw).strip()
        result = json.loads(clean)
    except Exception as e:
        return jsonify({"error": str(e)}), 500

    # Store full result in session
    session_id = str(uuid.uuid4())
    sessions[session_id] = {"result": result, "paid": False}

    # Return free preview (strip paid sections)
    preview = {k: result[k] for k in [
        "name","role","overall_score","ai_susceptibility_score",
        "ai_augment_score","cv_sections","role_breakdown",
        "automation_risk","job_fit","strengths"
    ] if k in result}

    return jsonify({"session_id": session_id, "preview": preview})


@app.route("/api/create-order", methods=["POST"])
def create_order():
    data = request.get_json()
    session_id = data.get("session_id")
    email      = (data.get("email") or "").strip().lower()

    if not session_id or session_id not in sessions:
        return jsonify({"error": "Invalid session"}), 400
    if not email or "@" not in email:
        return jsonify({"error": "Valid email address required"}), 400

    sessions[session_id]["email"] = email

    try:
        order = razorpay_client.order.create({
            "amount":   REPORT_PRICE_PAISE,
            "currency": "INR",
            "receipt":  f"wm_{session_id[:8]}",
            "notes":    {"session_id": session_id, "email": email}
        })
        sessions[session_id]["order_id"] = order["id"]
        return jsonify({"order_id": order["id"], "amount": REPORT_PRICE_PAISE,
                        "currency": "INR", "key": RAZORPAY_KEY_ID})
    except Exception as e:
        return jsonify({"error": str(e)}), 500


@app.route("/api/verify-payment", methods=["POST"])
def verify_payment():
    data = request.get_json()
    session_id       = data.get("session_id")
    payment_id       = data.get("razorpay_payment_id")
    order_id         = data.get("razorpay_order_id")
    signature        = data.get("razorpay_signature")

    if not all([session_id, payment_id, order_id, signature]):
        return jsonify({"error": "Missing payment data"}), 400

    # Verify Razorpay signature
    body   = f"{order_id}|{payment_id}"
    expected_sig = hmac.new(
        RAZORPAY_KEY_SECRET.encode(),
        body.encode(), hashlib.sha256
    ).hexdigest()

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

    # Read PDF as base64 for direct browser download (survives stateless deploys)
    pdf_b64 = ""
    try:
        with open(pdf_path, "rb") as f:
            pdf_b64 = base64.b64encode(f.read()).decode("utf-8")
    except Exception:
        pass

    # Send email with PDF attachment
    email       = session.get("email", "")
    name        = full_result.get("name", "Professional")
    role        = full_result.get("role", "–")
    email_sent  = False
    email_error = ""

    if email:
        ok, msg = send_report_email(email, name, role, full_result, pdf_path)
        email_sent  = ok
        email_error = "" if ok else msg

    # Return full data
    paid_sections = {k: full_result[k] for k in [
        "strategic_position","upskilling_roadmap",
        "top_improvements","ai_systems"
    ] if k in full_result}

    return jsonify({
        "success":       True,
        "paid_sections": paid_sections,
        "download_url":  f"/api/download/{session_id}",
        "pdf_b64":       pdf_b64,
        "pdf_name":      f"WorkMoat_Report_{name.replace(' ','_')}.pdf",
        "email_sent":    email_sent,
        "email":         email,
        "email_error":   email_error
    })


@app.route("/api/download/<session_id>")
def download_report(session_id):
    session = sessions.get(session_id)
    if not session or not session.get("paid"):
        return jsonify({"error": "Unauthorized"}), 403
    pdf_path = session.get("pdf_path")
    if not pdf_path or not os.path.exists(pdf_path):
        return jsonify({"error": "Report not found"}), 404
    name = session["result"].get("name", "report").replace(" ", "_")
    return send_file(pdf_path, as_attachment=True,
                     download_name=f"WorkMoat_Report_{name}.pdf",
                     mimetype="application/pdf")


if __name__ == "__main__":
    app.run(debug=True, port=5000)

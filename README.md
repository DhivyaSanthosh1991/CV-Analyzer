# WorkMoat — CV + AI Risk Analyser
## Setup

### 1. Install dependencies
```bash
pip install -r requirements.txt
```

### 2. Set environment variables
Create a `.env` file (never commit this):
```
ANTHROPIC_API_KEY=sk-ant-...
RAZORPAY_KEY_ID=rzp_live_...
RAZORPAY_KEY_SECRET=your_secret_here
SENDGRID_API_KEY=SG.xxxxxx
FROM_EMAIL=reports@yourdomain.com
```

Or export them directly:
```bash
export ANTHROPIC_API_KEY=sk-ant-...
export RAZORPAY_KEY_ID=rzp_live_...
export RAZORPAY_KEY_SECRET=your_secret_here
```

### 3. Run locally
```bash
python app.py
# Visit http://localhost:5000
```

### 4. Production deploy (Render / Railway / VPS)
```bash
gunicorn app:app --bind 0.0.0.0:$PORT --workers 2
```

---

## Project structure
```
workmoat/
├── app.py              ← Flask backend (API routes + Razorpay)
├── pdf_generator.py    ← ReportLab PDF report builder
├── requirements.txt    ← Python dependencies
├── templates/
│   └── index.html      ← Full frontend (hero + upload + results + payment)
└── reports/            ← Generated PDFs (auto-created, gitignore this)
```

## API Endpoints

| Method | Route | Description |
|--------|-------|-------------|
| GET  | `/` | Serves the frontend |
| POST | `/api/analyse` | Analyses CV text, returns free preview + session_id |
| POST | `/api/create-order` | Creates Razorpay order for ₹199 |
| POST | `/api/verify-payment` | Verifies Razorpay signature, unlocks full report + generates PDF |
| GET  | `/api/download/<session_id>` | Downloads the generated PDF (auth gated) |

## Razorpay setup
1. Sign up at https://razorpay.com
2. Go to Settings → API Keys → Generate Key
3. Use `rzp_test_...` keys for testing, `rzp_live_...` for production
4. Add your domain to the Razorpay dashboard whitelist

## Production notes
- Replace in-memory `sessions` dict with Redis or a DB (PostgreSQL/SQLite)
- Add rate limiting (Flask-Limiter)
- Store PDFs in S3/Cloudflare R2 instead of local filesystem
- Add HTTPS (Nginx + Let's Encrypt or use a platform like Render)

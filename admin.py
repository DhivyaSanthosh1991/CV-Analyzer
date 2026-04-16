import os, io, base64, json, zipfile
from datetime import datetime
from flask import Blueprint, request, jsonify, send_file, render_template_string, abort
from database import get_db, _exec, _row, _rows, DATABASE_URL

admin_bp = Blueprint("admin", __name__)

# ── Secret key from env ───────────────────────────────────────────────────────
ADMIN_SECRET = os.getenv("ADMIN_SECRET_KEY", "workmoat-admin-change-this")


def check_secret(key):
    return key == ADMIN_SECRET


# ── Admin HTML template ───────────────────────────────────────────────────────
ADMIN_HTML = """<!DOCTYPE html>
<html lang="en">
<head>
<meta charset="UTF-8"/>
<meta name="viewport" content="width=device-width,initial-scale=1"/>
<title>WorkMoat Admin</title>
<link href="https://fonts.googleapis.com/css2?family=Syne:wght@400;600;700&family=DM+Sans:wght@300;400;500&display=swap" rel="stylesheet"/>
<style>
*{box-sizing:border-box;margin:0;padding:0}
body{font-family:'DM Sans',sans-serif;background:#f9f7f2;color:#1a1a18;font-size:14px}
:root{--teal:#1e7f8a;--teal2:#165f68;--teal-bg:#e8f5f6;--teal-bd:#a8dde2;
  --border:#ddd9ce;--border2:#ccc8bb;--bg:#f9f7f2;--bg1:#fff;--bg2:#f2f0ea;
  --ink:#1a1a18;--ink2:#3d3b34;--ink3:#6b6860;--ink4:#9e9b91;
  --green:#1a7a45;--gbg:#edf7f1;--gbd:#9fd4b5;
  --red:#a02020;--rbg:#fdf0f0;--rbd:#f0a0a0;
  --amber:#a05c10;--abg:#fef4e6;--abd:#f5c87a;--r:8px;--rlg:12px}

nav{background:var(--bg1);border-bottom:1px solid var(--border);padding:0 32px;height:56px;display:flex;align-items:center;justify-content:space-between;position:sticky;top:0;z-index:100}
.nav-brand{font-family:'Syne',sans-serif;font-size:14px;font-weight:700;color:var(--ink)}
.nav-brand span{color:var(--teal)}
.nav-badge{font-family:'Syne',sans-serif;font-size:9px;font-weight:700;letter-spacing:.1em;text-transform:uppercase;background:var(--rbg);color:var(--red);border:1px solid var(--rbd);border-radius:100px;padding:3px 10px}

.container{max-width:1200px;margin:0 auto;padding:28px 24px}
.page-title{font-family:'Syne',sans-serif;font-size:22px;font-weight:700;color:var(--ink);margin-bottom:4px}
.page-sub{font-size:13px;color:var(--ink4);font-weight:300;margin-bottom:28px}

.stats-row{display:grid;grid-template-columns:repeat(auto-fit,minmax(160px,1fr));gap:12px;margin-bottom:28px}
.stat{background:var(--bg1);border:1px solid var(--border);border-radius:var(--rlg);padding:18px 16px;text-align:center}
.stat-n{font-family:'Syne',sans-serif;font-size:28px;font-weight:700;color:var(--teal);line-height:1;margin-bottom:4px}
.stat-l{font-size:11px;color:var(--ink4);font-weight:300;text-transform:uppercase;letter-spacing:.06em;font-family:'Syne',sans-serif}

.section{background:var(--bg1);border:1px solid var(--border);border-radius:var(--rlg);margin-bottom:20px;overflow:hidden}
.section-head{padding:14px 20px;border-bottom:1px solid var(--border);display:flex;align-items:center;justify-content:space-between;background:var(--bg2)}
.section-title{font-family:'Syne',sans-serif;font-size:11px;font-weight:700;letter-spacing:.1em;text-transform:uppercase;color:var(--ink3)}
.section-actions{display:flex;gap:8px}

.btn{font-family:'Syne',sans-serif;font-size:10px;font-weight:700;letter-spacing:.07em;text-transform:uppercase;padding:6px 14px;border-radius:100px;border:1px solid var(--border);background:var(--bg1);color:var(--ink3);cursor:pointer;transition:all .15s;text-decoration:none;display:inline-block}
.btn:hover{border-color:var(--teal-bd);color:var(--teal);background:var(--teal-bg)}
.btn.primary{background:var(--teal);color:#fff;border-color:var(--teal)}
.btn.primary:hover{background:var(--teal2);color:#fff}
.btn.danger:hover{border-color:var(--rbd);color:var(--red);background:var(--rbg)}

table{width:100%;border-collapse:collapse}
th{font-family:'Syne',sans-serif;font-size:9px;font-weight:700;letter-spacing:.1em;text-transform:uppercase;color:var(--ink4);padding:10px 16px;text-align:left;border-bottom:1px solid var(--border)}
td{padding:10px 16px;border-bottom:1px solid var(--border);vertical-align:middle;font-size:13px;color:var(--ink2)}
tr:last-child td{border-bottom:none}
tr:hover td{background:var(--bg2)}

.badge{font-family:'Syne',sans-serif;font-size:9px;font-weight:700;letter-spacing:.05em;text-transform:uppercase;padding:2px 8px;border-radius:100px}
.badge.paid{background:var(--gbg);color:var(--green);border:1px solid var(--gbd)}
.badge.free{background:var(--bg2);color:var(--ink4);border:1px solid var(--border)}
.badge.high{background:var(--rbg);color:var(--red);border:1px solid var(--rbd)}
.badge.medium{background:var(--abg);color:var(--amber);border:1px solid var(--abd)}
.badge.low{background:var(--gbg);color:var(--green);border:1px solid var(--gbd)}

.score-pill{font-family:'Syne',sans-serif;font-size:11px;font-weight:700;padding:2px 8px;border-radius:100px}
.search-bar{display:flex;gap:10px;padding:12px 16px;border-bottom:1px solid var(--border);background:var(--bg2)}
.search-bar input{flex:1;font-size:13px;font-family:'DM Sans',sans-serif;padding:7px 12px;border-radius:var(--r);border:1px solid var(--border);background:var(--bg1);color:var(--ink);outline:none}
.search-bar input:focus{border-color:var(--teal)}
.tabs{display:flex;gap:2px;padding:12px 16px 0;border-bottom:1px solid var(--border)}
.tab{font-family:'Syne',sans-serif;font-size:10px;font-weight:700;letter-spacing:.07em;text-transform:uppercase;padding:8px 16px;border-radius:var(--r) var(--r) 0 0;border:1px solid transparent;cursor:pointer;color:var(--ink4);background:none;transition:all .15s}
.tab.active{background:var(--bg1);color:var(--teal);border-color:var(--border);border-bottom-color:var(--bg1);position:relative;top:1px}
.empty{text-align:center;padding:40px;color:var(--ink4);font-family:'Syne',sans-serif;font-size:11px;font-weight:600;letter-spacing:.1em;text-transform:uppercase}
.spinner{display:inline-block;width:16px;height:16px;border:2px solid var(--border2);border-top-color:var(--teal);border-radius:50%;animation:spin .6s linear infinite;vertical-align:middle;margin-right:8px}
@keyframes spin{to{transform:rotate(360deg)}}

.user-avatar{width:30px;height:30px;border-radius:50%;background:var(--teal);display:inline-flex;align-items:center;justify-content:center;font-family:'Syne',sans-serif;font-size:11px;font-weight:700;color:#fff;flex-shrink:0;vertical-align:middle;margin-right:8px}
.truncate{max-width:180px;white-space:nowrap;overflow:hidden;text-overflow:ellipsis}
</style>
</head>
<body>
<nav>
  <span class="nav-brand">Work<span>Moat.ai</span></span>
  <span class="nav-badge">Admin Panel</span>
</nav>

<div class="container">
  <div class="page-title">Admin Dashboard</div>
  <div class="page-sub">Manage all users, CVs, and reports · <span id="last-refresh" style="color:var(--teal)"></span></div>

  <div class="stats-row" id="stats-row">
    <div class="stat"><div class="spin" style="margin:8px auto;width:20px;height:20px;border:2px solid #ddd;border-top-color:#1e7f8a;border-radius:50%;animation:spin .6s linear infinite"></div></div>
  </div>

  <div class="section">
    <div class="tabs">
      <button class="tab active" onclick="switchTab('users')">Users</button>
      <button class="tab" onclick="switchTab('cvs')">CV uploads</button>
      <button class="tab" onclick="switchTab('reports')">Reports</button>
    </div>

    <div class="search-bar">
      <input type="text" id="search-input" placeholder="Search by name, email, filename…" oninput="filterTable()"/>
      <button class="btn primary" onclick="exportZip()" id="export-btn">⬇ Export all CVs (ZIP)</button>
    </div>

    <div id="tab-content"></div>
  </div>
</div>

<script>
const SECRET = '{{ secret }}';
let currentTab = 'users';
let allData = { users:[], cvs:[], reports:[] };

async function api(path) {
  const r = await fetch(path + '?key=' + SECRET);
  return r.json();
}

async function loadAll() {
  document.getElementById('last-refresh').textContent = 'Loading…';
  const [stats, users, cvs, reports] = await Promise.all([
    api('/admin/api/stats'),
    api('/admin/api/users'),
    api('/admin/api/cvs'),
    api('/admin/api/reports'),
  ]);
  renderStats(stats);
  allData = { users, cvs, reports };
  renderTab(currentTab);
  document.getElementById('last-refresh').textContent = 'Last refreshed: ' + new Date().toLocaleTimeString();
}

function renderStats(s) {
  document.getElementById('stats-row').innerHTML = [
    ['Total users', s.total_users],
    ['CVs uploaded', s.total_cvs],
    ['Total reports', s.total_reports],
    ['Paid reports', s.paid_reports],
    ['Revenue (₹)', '₹' + (s.paid_reports * 199).toLocaleString()],
    ['Storage used', (s.total_storage_mb||0) + ' MB'],
  ].map(([l,v])=>`<div class="stat"><div class="stat-n">${v}</div><div class="stat-l">${l}</div></div>`).join('');
}

function switchTab(tab) {
  currentTab = tab;
  document.querySelectorAll('.tab').forEach((t,i)=>{
    t.classList.toggle('active', ['users','cvs','reports'][i]===tab);
  });
  document.getElementById('search-input').value = '';
  renderTab(tab);
}

function filterTable() {
  const q = document.getElementById('search-input').value.toLowerCase();
  renderTab(currentTab, q);
}

function renderTab(tab, q='') {
  const el = document.getElementById('tab-content');
  if (tab === 'users')   el.innerHTML = renderUsers(allData.users, q);
  if (tab === 'cvs')     el.innerHTML = renderCVs(allData.cvs, q);
  if (tab === 'reports') el.innerHTML = renderReports(allData.reports, q);
}

function renderUsers(users, q) {
  const filtered = users.filter(u =>
    !q || u.email?.toLowerCase().includes(q) || u.name?.toLowerCase().includes(q));
  if (!filtered.length) return '<div class="empty">No users found</div>';
  return `<table>
    <thead><tr>
      <th>User</th><th>Email</th><th>CVs</th><th>Reports</th><th>Paid</th><th>Joined</th>
    </tr></thead>
    <tbody>${filtered.map(u => {
      const initials = (u.name||u.email||'?').split(' ').map(w=>w[0]).join('').toUpperCase().slice(0,2);
      const date = u.created_at ? new Date(u.created_at).toLocaleDateString('en-IN',{day:'numeric',month:'short',year:'numeric'}) : '–';
      return `<tr>
        <td><span class="user-avatar">${initials}</span>${u.name||'–'}</td>
        <td style="color:var(--teal)">${u.email}</td>
        <td>${u.cv_count||0}</td>
        <td>${u.report_count||0}</td>
        <td>${u.paid_count||0 ? `<span class="badge paid">${u.paid_count} paid</span>` : '–'}</td>
        <td style="color:var(--ink4)">${date}</td>
      </tr>`;
    }).join('')}</tbody>
  </table>`;
}

function renderCVs(cvs, q) {
  const filtered = cvs.filter(c =>
    !q || c.filename?.toLowerCase().includes(q) ||
          c.user_email?.toLowerCase().includes(q) ||
          c.user_name?.toLowerCase().includes(q) ||
          c.job_title?.toLowerCase().includes(q));
  if (!filtered.length) return '<div class="empty">No CVs found</div>';
  return `<table>
    <thead><tr>
      <th>File</th><th>User</th><th>Job title</th><th>Size</th><th>Uploaded</th><th>Score</th><th>Actions</th>
    </tr></thead>
    <tbody>${filtered.map(c => {
      const date = c.created_at ? new Date(c.created_at).toLocaleDateString('en-IN',{day:'numeric',month:'short',year:'numeric'}) : '–';
      const size = c.file_size_kb >= 1024 ? (c.file_size_kb/1024).toFixed(1)+' MB' : (c.file_size_kb||0).toFixed(0)+' KB';
      const ext  = (c.file_type||'txt').toUpperCase();
      const scoreColor = c.overall_score>=70?'var(--green)':c.overall_score>=40?'var(--amber)':'var(--red)';
      return `<tr>
        <td><strong>${ext}</strong> <span class="truncate" style="display:inline-block">${c.filename||'pasted'}</span></td>
        <td style="color:var(--teal)">${c.user_email||'Anonymous'}<br><span style="font-size:11px;color:var(--ink4)">${c.user_name||''}</span></td>
        <td style="color:var(--ink3)">${c.job_title||'–'}</td>
        <td style="color:var(--ink4)">${size}</td>
        <td style="color:var(--ink4)">${date}</td>
        <td>${c.overall_score ? `<span style="font-family:Syne,sans-serif;font-size:13px;font-weight:700;color:${scoreColor}">${c.overall_score}</span>` : '–'}</td>
        <td><button class="btn" onclick="downloadCV(${c.id})">⬇ Download</button></td>
      </tr>`;
    }).join('')}</tbody>
  </table>`;
}

function renderReports(reports, q) {
  const filtered = reports.filter(r =>
    !q || r.name?.toLowerCase().includes(q) ||
          r.role?.toLowerCase().includes(q) ||
          r.user_email?.toLowerCase().includes(q));
  if (!filtered.length) return '<div class="empty">No reports found</div>';
  return `<table>
    <thead><tr>
      <th>Name</th><th>Role</th><th>User</th><th>CV score</th><th>AI risk</th><th>Status</th><th>Date</th><th>PDF</th>
    </tr></thead>
    <tbody>${filtered.map(r => {
      const date = r.created_at ? new Date(r.created_at).toLocaleDateString('en-IN',{day:'numeric',month:'short',year:'numeric'}) : '–';
      const oCol = r.overall_score>=70?'var(--green)':r.overall_score>=40?'var(--amber)':'var(--red)';
      const sCol = r.ai_susceptibility_score>=70?'var(--red)':r.ai_susceptibility_score>=40?'var(--amber)':'var(--green)';
      const riskLvl = r.automation_risk_level||'';
      return `<tr>
        <td><strong>${r.name||'–'}</strong></td>
        <td style="color:var(--ink3)">${r.role||'–'}</td>
        <td style="color:var(--teal);font-size:12px">${r.user_email||'Anonymous'}</td>
        <td><span style="font-family:Syne,sans-serif;font-size:13px;font-weight:700;color:${oCol}">${r.overall_score||'–'}</span></td>
        <td><span style="font-family:Syne,sans-serif;font-size:13px;font-weight:700;color:${sCol}">${r.ai_susceptibility_score||'–'}</span>
            ${riskLvl?`<span class="badge ${riskLvl}" style="margin-left:4px">${riskLvl}</span>`:''}</td>
        <td>${r.paid ? '<span class="badge paid">Paid</span>' : '<span class="badge free">Free</span>'}</td>
        <td style="color:var(--ink4)">${date}</td>
        <td>${r.paid ? `<button class="btn" onclick="downloadPDF('${r.session_id}','${(r.name||'report').replace(/'/g,'')}')">⬇ PDF</button>` : '–'}</td>
      </tr>`;
    }).join('')}</tbody>
  </table>`;
}

async function downloadCV(uploadId) {
  const btn = event.target;
  btn.disabled=true; btn.textContent='Loading…';
  try {
    const r   = await fetch('/admin/api/cv/'+uploadId+'?key='+SECRET);
    const cv  = await r.json();
    if (cv.error) { alert(cv.error); return; }
    if (cv.file_b64 && cv.file_b64.length > 10) {
      triggerDownload(cv.file_b64, cv.filename || 'cv.txt', 'base64');
    } else {
      triggerDownload(cv.extracted_text||'', cv.filename||'cv.txt', 'text');
    }
  } catch(e) { alert('Error: '+e.message); }
  btn.disabled=false; btn.textContent='⬇ Download';
}

async function downloadPDF(sessionId, name) {
  const btn = event.target;
  btn.disabled=true; btn.textContent='Loading…';
  try {
    const r    = await fetch('/admin/api/report-pdf/'+sessionId+'?key='+SECRET);
    const data = await r.json();
    if (data.error) { alert(data.error); return; }
    triggerDownload(data.pdf_b64, 'WorkMoat_Report_'+name.replace(/ /g,'_')+'.pdf', 'base64');
  } catch(e) { alert('Error: '+e.message); }
  btn.disabled=false; btn.textContent='⬇ PDF';
}

function triggerDownload(data, filename, type) {
  let url;
  if (type === 'base64') {
    const bytes = atob(data);
    const arr   = new Uint8Array(bytes.length);
    for (let i=0; i<bytes.length; i++) arr[i] = bytes.charCodeAt(i);
    const ext   = filename.split('.').pop().toLowerCase();
    const mime  = ext==='pdf' ? 'application/pdf'
                : ext==='docx' ? 'application/vnd.openxmlformats-officedocument.wordprocessingml.document'
                : 'application/octet-stream';
    url = URL.createObjectURL(new Blob([arr], {type:mime}));
  } else {
    url = URL.createObjectURL(new Blob([data], {type:'text/plain'}));
  }
  const a = document.createElement('a'); a.href=url; a.download=filename;
  document.body.appendChild(a); a.click();
  setTimeout(()=>{URL.revokeObjectURL(url);document.body.removeChild(a)},2000);
}

async function exportZip() {
  const btn = document.getElementById('export-btn');
  btn.disabled=true; btn.textContent='Preparing ZIP…';
  try {
    const r = await fetch('/admin/api/export-zip?key='+SECRET);
    if (!r.ok) { alert('Export failed'); return; }
    const blob = await r.blob();
    const url  = URL.createObjectURL(blob);
    const a    = document.createElement('a'); a.href=url;
    a.download = 'WorkMoat_CVs_'+new Date().toISOString().slice(0,10)+'.zip';
    document.body.appendChild(a); a.click();
    setTimeout(()=>{URL.revokeObjectURL(url);document.body.removeChild(a)},2000);
  } catch(e) { alert('Export error: '+e.message); }
  btn.disabled=false; btn.textContent='⬇ Export all CVs (ZIP)';
}

loadAll();
setInterval(loadAll, 60000); // auto-refresh every 60s
</script>
</body>
</html>
"""


# ── Admin API routes ──────────────────────────────────────────────────────────

def require_admin(f):
    from functools import wraps
    @wraps(f)
    def decorated(*args, **kwargs):
        key = request.args.get("key") or request.headers.get("X-Admin-Key", "")
        if not check_secret(key):
            abort(403)
        return f(*args, **kwargs)
    return decorated


@admin_bp.route("/admin/<secret_key>")
def admin_panel(secret_key):
    if not check_secret(secret_key):
        abort(404)   # return 404 not 403 — don't reveal the panel exists
    return render_template_string(ADMIN_HTML, secret=secret_key)


@admin_bp.route("/admin/api/stats")
@require_admin
def admin_stats():
    stats = {}
    stats["total_users"]      = (_exec("SELECT COUNT(*) as c FROM users",      fetchone=True) or {}).get("c", 0)
    stats["total_cvs"]        = (_exec("SELECT COUNT(*) as c FROM cv_uploads", fetchone=True) or {}).get("c", 0)
    stats["total_reports"]    = (_exec("SELECT COUNT(*) as c FROM reports",    fetchone=True) or {}).get("c", 0)
    stats["paid_reports"]     = (_exec("SELECT COUNT(*) as c FROM reports WHERE paid=1", fetchone=True) or {}).get("c", 0)
    r = _exec("SELECT ROUND(SUM(file_size_kb)/1024.0,2) as s FROM cv_uploads", fetchone=True)
    stats["total_storage_mb"] = (r or {}).get("s") or 0
    return jsonify(stats)


@admin_bp.route("/admin/api/users")
@require_admin
def admin_users():
    rows = _exec("""
        SELECT u.id, u.email, u.name, u.created_at, u.last_login,
               COUNT(DISTINCT c.id) as cv_count,
               COUNT(DISTINCT r.id) as report_count,
               SUM(CASE WHEN r.paid=1 THEN 1 ELSE 0 END) as paid_count
        FROM users u
        LEFT JOIN cv_uploads c ON c.user_id = u.id
        LEFT JOIN reports    r ON r.user_id = u.id
        GROUP BY u.id
        ORDER BY u.created_at DESC
    """, fetchall=True)
    return jsonify(_rows(rows))


@admin_bp.route("/admin/api/cvs")
@require_admin
def admin_cvs():
    rows = _exec("""
        SELECT c.id, c.filename, c.file_type, c.file_size_kb,
               c.job_title, c.industry, c.upload_source, c.created_at,
               substr(c.extracted_text, 1, 300) as text_preview,
               u.email as user_email, u.name as user_name,
               r.overall_score, r.ai_susceptibility_score, r.paid as report_paid
        FROM cv_uploads c
        LEFT JOIN users   u ON u.id = c.user_id
        LEFT JOIN reports r ON r.cv_upload_id = c.id
        ORDER BY c.created_at DESC
    """, fetchall=True)
    return jsonify(_rows(rows))


@admin_bp.route("/admin/api/reports")
@require_admin
def admin_reports():
    rows = _exec("""
        SELECT r.id, r.session_id, r.name, r.role,
               r.overall_score, r.ai_susceptibility_score, r.ai_augment_score,
               r.automation_risk_level, r.paid, r.created_at,
               u.email as user_email, u.name as user_name
        FROM reports r
        LEFT JOIN users u ON u.id = r.user_id
        ORDER BY r.created_at DESC
    """, fetchall=True)
    return jsonify(_rows(rows))


@admin_bp.route("/admin/api/cv/<int:upload_id>")
@require_admin
def admin_get_cv(upload_id):
    P = "%" + "s" if DATABASE_URL else "?"
    row = _exec(f"SELECT * FROM cv_uploads WHERE id={P}", (upload_id,), fetchone=True)
    if not row:
        return jsonify({"error": "CV not found"}), 404
    return jsonify(_row(row))


@admin_bp.route("/admin/api/report-pdf/<session_id>")
@require_admin
def admin_get_report_pdf(session_id):
    P = "%" + "s" if DATABASE_URL else "?"
    row = _exec(f"SELECT pdf_b64, name FROM reports WHERE session_id={P} AND paid=1",
                (session_id,), fetchone=True)
    if not row or not (row.get("pdf_b64")):
        return jsonify({"error": "PDF not found or report not paid"}), 404
    return jsonify(_row(row))


@admin_bp.route("/admin/api/export-zip")
@require_admin
def admin_export_zip():
    """Export all CV files as a ZIP — streamed directly."""
    rows = _exec("""
        SELECT c.id, c.filename, c.file_type, c.file_b64, c.extracted_text,
               c.created_at, u.email as user_email, u.name as user_name,
               c.job_title
        FROM cv_uploads c
        LEFT JOIN users u ON u.id = c.user_id
        ORDER BY c.created_at DESC
    """, fetchall=True)
    rows = [dict(r) for r in (rows or [])]

    buf = io.BytesIO()
    manifest_lines = ["id,filename,user_email,user_name,job_title,uploaded_at"]

    with zipfile.ZipFile(buf, "w", zipfile.ZIP_DEFLATED) as zf:
        for row in rows:
            d        = dict(row)
            date_str = (d.get("created_at") or "")[:10]
            email    = (d.get("user_email") or "anonymous").replace("@","_at_").replace(".","_")
            safe_fn  = (d.get("filename") or "cv").replace("/","_").replace("\\","_")
            zip_name = f"{date_str}/{email}/{d['id']}_{safe_fn}"

            if d.get("file_b64") and len(d["file_b64"]) > 20:
                try:
                    file_bytes = base64.b64decode(d["file_b64"])
                    zf.writestr(zip_name, file_bytes)
                except Exception:
                    pass
            elif d.get("extracted_text"):
                zf.writestr(zip_name + ".txt", d["extracted_text"])

            manifest_lines.append(",".join([
                str(d["id"]),
                safe_fn,
                d.get("user_email") or "anonymous",
                d.get("user_name") or "",
                d.get("job_title") or "",
                date_str,
            ]))

        zf.writestr("_manifest.csv", "\n".join(manifest_lines))

    buf.seek(0)
    filename = f"WorkMoat_CVs_{datetime.now().strftime('%Y-%m-%d')}.zip"
    return send_file(buf, as_attachment=True, download_name=filename,
                     mimetype="application/zip")

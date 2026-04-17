"""WorkMoat PDF Generator — HTML→PDF via WeasyPrint"""
from datetime import datetime

def score_color(score, kind="quality"):
    if kind in ("susceptibility", "risk"):
        if score >= 76: return "#C0392B"
        if score >= 56: return "#D35400"
        if score >= 31: return "#D4AC0D"
        return "#27AE60"
    elif kind == "augment":
        if score >= 70: return "#27AE60"
        if score >= 40: return "#D4AC0D"
        return "#C0392B"
    else:
        if score >= 70: return "#27AE60"
        if score >= 40: return "#D4AC0D"
        return "#C0392B"

def badge_style(priority):
    p = priority.lower()
    if p == "high":   return "background:#C0392B;color:#fff"
    if p == "medium": return "background:#D35400;color:#fff"
    return "background:#27AE60;color:#fff"

def build_html(result):
    name    = result.get("name", "Professional")
    role    = result.get("role", "")
    today   = datetime.now().strftime("%d %b %Y")
    ar      = result.get("automation_risk") or {}
    moat    = result.get("career_moat") or {}
    bd      = result.get("cv_breakdown") or {}
    action  = result.get("action_plan") or {}

    # Score grid
    scores = [
        (result.get("overall_score", 0),           "CV quality",           "quality"),
        (result.get("ai_susceptibility_score", 0), "AI susceptibility",    "susceptibility"),
        (result.get("ai_augment_score", 0),        "AI augment potential", "augment"),
        (result.get("job_fit_score", 0),           "Job fit",              "quality"),
        (ar.get("score", 0),                       "AI automation risk",   "risk"),
    ]
    score_cells = ""
    for val, lbl, kind in scores:
        col = score_color(val, kind)
        score_cells += f'<div class="score-cell"><div class="score-num" style="color:{col}">{val}</div><div class="score-lbl">{lbl}</div></div>'

    # CV Breakdown
    bd_rows = ""
    for lbl, key in [("Contact & Visibility","contact"),("Professional Summary","summary"),
                      ("Experience & Impact","experience"),("Skills Relevance","skills"),
                      ("Formatting & ATS","formatting")]:
        val = bd.get(key, 0)
        col = score_color(val, "quality")
        bd_rows += f'<div class="bd-row"><div class="bd-label">{lbl}</div><div class="bd-bar-wrap"><div class="bd-bar" style="width:{val}%;background:{col}"></div></div><div class="bd-score" style="color:{col}">{val}</div></div>'

    # Chips
    def chips(items, cls="chip"):
        return " ".join([f'<span class="{cls}">{i}</span>' for i in items])

    strengths   = chips(result.get("strengths", []))
    gaps_items  = "".join([f"<li>{g}</li>" for g in result.get("gaps", [])])
    risk_tasks  = chips(ar.get("at_risk_tasks", []), "chip-risk")
    human_chips = chips(result.get("human_edge", []), "chip-green")
    adopt_chips = chips(result.get("ai_tools_to_adopt", []), "chip-teal")

    # AI tools table
    ai_rows = ""
    for tool in result.get("ai_tools_replacing", []):
        parts = tool.split(" — ", 1) if " — " in tool else [tool, "Assisting tasks in this role"]
        ai_rows += f'<tr><td class="td-tool">{parts[0]}</td><td>{parts[1] if len(parts)>1 else ""}</td></tr>'

    # Moat box
    moat_rows = ""
    for label, key in [("Core Moat","core_strength"),("Primary Threat","the_threat"),("Strategic Move","one_move")]:
        val = moat.get(key, "")
        if val:
            moat_rows += f'<div class="moat-row"><span class="moat-label">{label}:</span> {val}</div>'

    # Roadmap
    roadmap_html = ""
    for item in result.get("upskilling_roadmap", []):
        pri = item.get("priority", "medium")
        bstyle = badge_style(pri)
        roadmap_html += f"""<div class="upskill-item p-{pri}">
          <div class="upskill-header"><span class="badge" style="{bstyle}">{pri.upper()}</span>
          <span class="upskill-title">{item.get("skill","")}</span></div>
          <div class="upskill-why"><em>Why this matters for you:</em> {item.get("why","")}</div>
          <div class="upskill-res">📚 {item.get("resources","")}</div>
        </div>"""

    # CV improvements
    imp_rows = ""
    for imp in result.get("cv_improvements", []):
        pri = imp.get("priority", "medium")
        bstyle = badge_style(pri)
        imp_rows += f'<tr><td style="text-align:center;padding:8px"><span class="badge" style="{bstyle}">{pri.upper()}</span></td><td style="padding:8px 10px">{imp.get("action","")}</td></tr>'

    # Action plan phases
    def phase(title, sub, items):
        items_html = "".join([f'<div class="action-item"><span class="chk">☐</span> {i}</div>' for i in items])
        return f'<div class="action-phase"><div class="phase-title">{title}</div><div class="phase-sub">{sub}</div>{items_html}</div>'

    phases = ""
    if action:
        phases  = phase("Days 1–30 · Protect", "Immediate defence — fix CV signal, deploy first AI workflows", action.get("days_1_30", []))
        phases += phase("Days 31–60 · Build",  "Deepen AI fluency, begin formal credentials, integrate AI", action.get("days_31_60", []))
        phases += phase("Days 61–90 · Grow",   "Produce AI-powered proof of capability, position for next role", action.get("days_61_90", []))

    risk_col  = score_color(ar.get("score", 0), "risk")
    risk_lvl  = ar.get("level", "moderate").upper()
    risk_tl   = ar.get("timeline", "")
    strat_dir = result.get("strategic_direction", "")

    return f"""<!DOCTYPE html><html lang="en"><head><meta charset="UTF-8"/>
<style>
@import url('https://fonts.googleapis.com/css2?family=Inter:wght@300;400;500;600;700&display=swap');
*{{box-sizing:border-box;margin:0;padding:0}}
body{{font-family:'Inter',Arial,sans-serif;color:#2C2C2C;background:#fff;font-size:10.5pt;line-height:1.6}}
.page{{max-width:800px;margin:0 auto;padding:44px 48px}}
.brand{{font-size:8.5pt;color:#AAA;letter-spacing:.5px;margin-bottom:5px}}
.rname{{font-size:20pt;font-weight:700;font-style:italic;color:#1a1a1a;margin-bottom:3px;line-height:1.2}}
.rmeta{{font-size:9.5pt;color:#999;margin-bottom:16px}}
hr.rule{{border:none;border-top:1px solid #E8E0D5;margin:14px 0}}
.score-grid{{display:flex;border:1px solid #E8E0D5;border-radius:4px;overflow:hidden;margin:18px 0}}
.score-cell{{flex:1;padding:14px 8px;text-align:center;border-right:1px solid #E8E0D5}}
.score-cell:last-child{{border-right:none}}
.score-num{{font-size:30pt;font-weight:700;line-height:1}}
.score-lbl{{font-size:7.5pt;color:#999;margin-top:4px;text-transform:uppercase;letter-spacing:.3px}}
.sec-head{{font-size:8pt;font-weight:700;letter-spacing:1.5px;text-transform:uppercase;color:#5C4A2A;border-bottom:1.5px solid #D8CEBC;padding-bottom:6px;margin:24px 0 12px}}
.bd-row{{display:flex;align-items:center;gap:10px;padding:5px 0;border-bottom:1px solid #F0E8DC}}
.bd-label{{font-size:9pt;color:#2C2C2C;width:165px;flex-shrink:0}}
.bd-bar-wrap{{flex:1;height:5px;background:#F0E8DC;border-radius:3px;overflow:hidden}}
.bd-bar{{height:100%;border-radius:3px}}
.bd-score{{font-size:9.5pt;font-weight:600;width:28px;text-align:right}}
.chip{{display:inline-block;background:#FAF7F3;border:1px solid #DDD8CC;border-radius:3px;padding:2px 8px;font-size:8.5pt;color:#5C4A2A;font-weight:600;margin:2px 3px}}
.chip-risk{{display:inline-block;background:#FDF0F0;border:1px solid #F0A0A0;border-radius:3px;padding:2px 8px;font-size:8.5pt;color:#C0392B;font-weight:500;margin:2px 3px}}
.chip-green{{display:inline-block;background:#EDF7F1;border:1px solid #9FD4B5;border-radius:3px;padding:2px 8px;font-size:8.5pt;color:#1A7A45;font-weight:500;margin:2px 3px}}
.chip-teal{{display:inline-block;background:#E8F5F6;border:1px solid #A8DDE2;border-radius:3px;padding:2px 8px;font-size:8.5pt;color:#1e7f8a;font-weight:500;margin:2px 3px}}
.badge{{display:inline-block;font-size:7.5pt;font-weight:700;letter-spacing:.8px;padding:2px 7px;border-radius:3px;text-transform:uppercase}}
.data-table{{width:100%;border-collapse:collapse;font-size:9.5pt;margin:10px 0}}
.data-table th{{text-align:left;font-size:7.5pt;font-weight:600;letter-spacing:.8px;text-transform:uppercase;color:#999;padding:6px 10px;background:#FAF7F3}}
.data-table td{{padding:7px 10px;border-bottom:1px solid #F0E8DC;vertical-align:top}}
.data-table tr:last-child td{{border-bottom:none}}
.td-tool{{font-weight:600;color:#5C4A2A;white-space:nowrap;min-width:180px}}
.moat-box{{background:#FAF7F3;border-left:3px solid #8B6914;padding:12px 16px;margin:10px 0;border-radius:0 4px 4px 0}}
.moat-row{{font-size:9.5pt;color:#444;margin:5px 0;line-height:1.6}}
.moat-label{{font-weight:700;color:#5C4A2A}}
.strat{{font-size:10pt;color:#444;line-height:1.7;margin-bottom:12px}}
.gaps-list{{padding-left:16px;margin:6px 0}}
.gaps-list li{{font-size:9.5pt;color:#555;margin:3px 0;line-height:1.6}}
.risk-box{{background:#FDF8F0;border:1px solid #E8D5A0;border-radius:4px;padding:10px 14px;margin:8px 0;font-size:9.5pt;color:#5C4A2A;line-height:1.7}}
.upskill-item{{padding:11px 13px;border:1px solid #E8E0D5;border-radius:4px;margin-bottom:7px}}
.p-high{{border-left:3px solid #C0392B}}
.p-medium{{border-left:3px solid #D35400}}
.p-low{{border-left:3px solid #27AE60}}
.upskill-header{{display:flex;align-items:center;gap:9px;margin-bottom:4px}}
.upskill-title{{font-size:10.5pt;font-weight:600;color:#1a1a1a}}
.upskill-why{{font-size:9pt;color:#555;margin:3px 0;line-height:1.6}}
.upskill-res{{font-size:9pt;color:#1e7f8a;margin-top:3px}}
.action-phase{{margin-bottom:14px;padding:12px 14px;background:#FAFAF8;border:1px solid #E8E0D5;border-radius:4px}}
.phase-title{{font-size:10.5pt;font-weight:700;color:#1a1a1a;margin-bottom:2px}}
.phase-sub{{font-size:8.5pt;color:#999;margin-bottom:8px;font-style:italic}}
.action-item{{font-size:9.5pt;color:#444;margin:4px 0;padding-left:4px;line-height:1.65}}
.chk{{color:#8B6914;font-weight:700;margin-right:5px}}
.footer{{font-size:8pt;color:#CCC;text-align:center;margin-top:28px;padding-top:14px;border-top:1px solid #EEE}}
.subhead{{font-size:8.5pt;font-weight:600;color:#555;margin:10px 0 5px}}
</style></head><body><div class="page">
  <div class="brand">workmoat.ai</div>
  <div class="rname">{name} — Full Diagnostic Report</div>
  <div class="rmeta">{role} · Generated {today}</div>
  <hr class="rule">
  <div class="score-grid">{score_cells}</div>
  <div class="sec-head">CV Quality Breakdown</div>
  {bd_rows}
  <div class="sec-head">Key Strengths</div>
  <div style="margin:6px 0">{strengths}</div>
  {"<div class='sec-head'>Key Gaps</div><ul class='gaps-list'>" + gaps_items + "</ul>" if gaps_items else ""}
  <div class="sec-head">AI Automation Risk</div>
  <div class="risk-box"><strong style="color:{risk_col}">✅ Risk Level: {risk_lvl}</strong>{"&nbsp;&nbsp;·&nbsp;&nbsp;Timeline: " + risk_tl if risk_tl else ""}</div>
  {"<div class='subhead'>AUTOMATION FRONTIER — Tasks with AI Assistance Potential</div><div style='margin:5px 0'>" + risk_tasks + "</div>" if risk_tasks else ""}
  {"<div class='subhead'>HUMAN EDGE — Tasks You Durably Own</div><div style='margin:5px 0'>" + human_chips + "</div>" if human_chips else ""}
  {"<div class='sec-head'>AI Systems Affecting This Role</div><div class='subhead'>Already assisting tasks in this role:</div><table class='data-table'><thead><tr><th>Tool / System</th><th>What It Assists</th></tr></thead><tbody>" + ai_rows + "</tbody></table>" if ai_rows else ""}
  {"<div class='subhead'>Tools to actively use to amplify output:</div><div style='margin:5px 0'>" + adopt_chips + "</div>" if adopt_chips else ""}
  <div class="sec-head">Strategic Position — Your Career Moat</div>
  {"<p class='strat'>" + strat_dir + "</p>" if strat_dir else ""}
  <div class="moat-box">{moat_rows}</div>
  <div class="sec-head">Upskilling Roadmap — Your Moat Builders</div>
  {roadmap_html}
  {"<div class='sec-head'>CV Improvement Suggestions</div><table class='data-table'><thead><tr><th>Priority</th><th>Action</th></tr></thead><tbody>" + imp_rows + "</tbody></table>" if imp_rows else ""}
  {"<div class='sec-head'>90-Day WorkMoat Action Plan</div>" + phases if phases else ""}
  <div class="footer">workmoat.ai · Confidential report for {name} · {today}<br>
  <span style="font-size:7.5pt">WorkMoat — Know your moat. Defend your career.</span></div>
</div></body></html>"""


def generate_report_pdf(result, output_path):
    try:
        from weasyprint import HTML, CSS
        html = build_html(result)
        HTML(string=html).write_pdf(
            output_path,
            stylesheets=[CSS(string="@page{size:A4;margin:0}")]
        )
    except Exception as e:
        print(f"WeasyPrint error: {e}, falling back to ReportLab")
        _reportlab_fallback(result, output_path)


def _reportlab_fallback(result, output_path):
    from reportlab.lib.pagesizes import A4
    from reportlab.lib.styles import ParagraphStyle
    from reportlab.lib.units import mm
    from reportlab.lib import colors
    from reportlab.platypus import SimpleDocTemplate, Paragraph, Spacer, HRFlowable
    name  = result.get("name","Professional")
    role  = result.get("role","")
    today = datetime.now().strftime("%d %b %Y")
    doc   = SimpleDocTemplate(output_path, pagesize=A4,
                               leftMargin=20*mm, rightMargin=20*mm,
                               topMargin=18*mm, bottomMargin=18*mm)
    def p(t, size=10, bold=False, color="#2C2C2C", after=6):
        s = ParagraphStyle("p", fontSize=size, textColor=colors.HexColor(color),
                            fontName="Helvetica-Bold" if bold else "Helvetica",
                            spaceAfter=after, leading=size*1.45)
        return Paragraph(t, s)
    story = [
        p("workmoat.ai", 8, color="#AAA"),
        p(f"{name} — Full Diagnostic Report", 18, bold=True),
        p(f"{role} · {today}", 10, color="#999"),
        HRFlowable(width="100%", thickness=0.5, color=colors.HexColor("#E8E0D5"), spaceAfter=10),
        p(f"CV Quality: {result.get('overall_score',0)}   AI Susceptibility: {result.get('ai_susceptibility_score',0)}   AI Augment: {result.get('ai_augment_score',0)}", 12, bold=True),
    ]
    moat = result.get("career_moat") or {}
    for k in ["core_strength","the_threat","one_move"]:
        if moat.get(k): story.append(p(f"• {moat[k]}", 10))
    for item in (result.get("upskilling_roadmap") or []):
        story.append(p(f"[{item.get('priority','').upper()}] {item.get('skill','')}: {item.get('why','')}", 9))
    story.append(HRFlowable(width="100%", thickness=0.5, color=colors.HexColor("#E8E0D5"), spaceBefore=16))
    story.append(p(f"workmoat.ai · {name} · {today}", 8, color="#CCC"))
    doc.build(story)

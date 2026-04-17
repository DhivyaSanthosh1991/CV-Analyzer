from reportlab.lib.pagesizes import A4
from reportlab.lib.styles import getSampleStyleSheet, ParagraphStyle
from reportlab.lib.units import mm
from reportlab.lib import colors
from reportlab.platypus import (
    SimpleDocTemplate, Paragraph, Spacer, Table, TableStyle,
    HRFlowable, KeepTogether
)
from reportlab.lib.enums import TA_LEFT, TA_CENTER, TA_RIGHT
from datetime import datetime

# ── Palette ───────────────────────────────────────────────────────────────────
BEIGE      = colors.HexColor("#FAF7F3")
DARK       = colors.HexColor("#2C2C2C")
MID        = colors.HexColor("#555555")
LIGHT      = colors.HexColor("#999999")
BORDER     = colors.HexColor("#E8E0D5")
GOLD       = colors.HexColor("#8B6914")
GREEN      = colors.HexColor("#27AE60")
AMBER      = colors.HexColor("#D4AC0D")
RED        = colors.HexColor("#C0392B")
ORANGE     = colors.HexColor("#D35400")
TEAL       = colors.HexColor("#1e7f8a")
SECTION_BG = colors.HexColor("#F5F0E8")
WHITE      = colors.white

W, H = A4
ML = MR = 20*mm
MT = MB = 18*mm

def score_color(score, kind="quality"):
    if kind in ("susceptibility", "risk"):
        if score >= 76: return RED
        if score >= 56: return ORANGE
        if score >= 31: return AMBER
        return GREEN
    elif kind == "augment":
        if score >= 70: return GREEN
        if score >= 40: return AMBER
        return RED
    else:  # quality, fit
        if score >= 70: return GREEN
        if score >= 40: return AMBER
        return RED

def score_label(score, kind="quality"):
    if kind in ("susceptibility", "risk"):
        if score >= 76: return "CRITICAL"
        if score >= 56: return "HIGH"
        if score >= 31: return "MODERATE"
        return "MANAGED"
    elif kind == "augment":
        if score >= 70: return "HIGH POTENTIAL"
        if score >= 40: return "MODERATE"
        return "LOW"
    else:
        if score >= 90: return "EXCELLENT"
        if score >= 70: return "STRONG"
        if score >= 40: return "MODERATE"
        return "NEEDS WORK"

def generate_report_pdf(result, output_path):
    doc = SimpleDocTemplate(
        output_path, pagesize=A4,
        leftMargin=ML, rightMargin=MR,
        topMargin=MT, bottomMargin=MB
    )

    styles = getSampleStyleSheet()
    def sty(name, **kw):
        return ParagraphStyle(name, parent=styles["Normal"], **kw)

    S = {
        "brand":    sty("brand",    fontSize=9,  textColor=LIGHT,  spaceAfter=4),
        "name":     sty("name",     fontSize=22, textColor=DARK,   fontName="Helvetica-Bold", spaceAfter=3),
        "meta":     sty("meta",     fontSize=10, textColor=LIGHT,  spaceAfter=14),
        "sec":      sty("sec",      fontSize=9,  textColor=GOLD,   fontName="Helvetica-Bold",
                        spaceBefore=18, spaceAfter=8, borderPadding=(0,0,4,0)),
        "body":     sty("body",     fontSize=10, textColor=MID,    spaceAfter=6, leading=15),
        "bold":     sty("bold",     fontSize=10, textColor=DARK,   fontName="Helvetica-Bold", spaceAfter=4),
        "small":    sty("small",    fontSize=8,  textColor=LIGHT),
        "moat":     sty("moat",     fontSize=10, textColor=MID,    leading=15, spaceAfter=5),
        "moatlbl":  sty("moatlbl",  fontSize=10, textColor=GOLD,   fontName="Helvetica-Bold"),
        "action":   sty("action",   fontSize=10, textColor=MID,    leading=15, spaceAfter=5, leftIndent=14),
        "phase":    sty("phase",    fontSize=11, textColor=DARK,   fontName="Helvetica-Bold", spaceBefore=12, spaceAfter=3),
        "phasesub": sty("phasesub", fontSize=9,  textColor=LIGHT,  spaceAfter=8),
        "footer":   sty("footer",   fontSize=8,  textColor=LIGHT,  alignment=TA_CENTER),
    }

    name   = result.get("name", "Professional")
    role   = result.get("role", "")
    today  = datetime.now().strftime("%d %b %Y")
    story  = []

    # ── Header ────────────────────────────────────────────────────────────────
    story.append(Paragraph("workmoat.ai", S["brand"]))
    story.append(Paragraph(f"{name} — Full Diagnostic Report", S["name"]))
    story.append(Paragraph(f"{role} · Generated {today}", S["meta"]))
    story.append(HRFlowable(width="100%", thickness=0.5, color=BORDER, spaceAfter=12))

    # ── Score grid ────────────────────────────────────────────────────────────
    scores = [
        (result.get("overall_score", 0),           "CV quality",           "quality"),
        (result.get("ai_susceptibility_score", 0), "AI susceptibility",    "susceptibility"),
        (result.get("ai_augment_score", 0),         "AI augment potential", "augment"),
        (result.get("job_fit_score", 0),            "Job fit",              "quality"),
        ((result.get("automation_risk") or {}).get("score", 0), "AI automation risk", "risk"),
    ]
    def score_cell(val, label, kind):
        col = score_color(val, kind)
        return [
            Paragraph(f'<font color="{col.hexval()}" size="28"><b>{val}</b></font>', sty("sc", alignment=TA_CENTER, fontSize=28)),
            Paragraph(label, sty("sl", fontSize=8, textColor=LIGHT, alignment=TA_CENTER))
        ]

    score_data = [[score_cell(v, l, k) for v, l, k in scores]]
    score_table = Table(score_data, colWidths=[(W-ML-MR)/5]*5)
    score_table.setStyle(TableStyle([
        ("BOX",        (0,0), (-1,-1), 0.5, BORDER),
        ("INNERGRID",  (0,0), (-1,-1), 0.5, BORDER),
        ("VALIGN",     (0,0), (-1,-1), "MIDDLE"),
        ("ALIGN",      (0,0), (-1,-1), "CENTER"),
        ("TOPPADDING", (0,0), (-1,-1), 10),
        ("BOTTOMPADDING",(0,0),(-1,-1), 10),
    ]))
    story.append(score_table)
    story.append(Spacer(1, 10))

    # ── CV Quality Breakdown ──────────────────────────────────────────────────
    breakdown = result.get("cv_breakdown", {})
    if breakdown:
        story.append(_section_head("CV QUALITY BREAKDOWN", S))
        bd_items = [
            ("Contact & Visibility", breakdown.get("contact", 0)),
            ("Professional Summary", breakdown.get("summary", 0)),
            ("Experience & Impact",  breakdown.get("experience", 0)),
            ("Skills Relevance",     breakdown.get("skills", 0)),
            ("Formatting & ATS",     breakdown.get("formatting", 0)),
        ]
        for label, score in bd_items:
            col = score_color(score, "quality")
            row_data = [
                Paragraph(label, sty("bdl", fontSize=9, textColor=DARK)),
                Paragraph(f'<font color="{col.hexval()}"><b>{score}</b></font>', sty("bds", fontSize=9, alignment=TA_RIGHT))
            ]
            t = Table([row_data], colWidths=[W-ML-MR-20*mm, 20*mm])
            t.setStyle(TableStyle([
                ("LINEBELOW", (0,0), (-1,-1), 0.3, BORDER),
                ("TOPPADDING", (0,0), (-1,-1), 4),
                ("BOTTOMPADDING", (0,0), (-1,-1), 4),
            ]))
            story.append(t)
        story.append(Spacer(1, 6))

    # ── Strengths ─────────────────────────────────────────────────────────────
    strengths = result.get("strengths", [])
    if strengths:
        story.append(_section_head("KEY STRENGTHS", S))
        chips = "   ".join([f"<b>{s}</b>" for s in strengths])
        story.append(Paragraph(chips, sty("chips", fontSize=9, textColor=GOLD, spaceAfter=8)))

    # ── Automation Risk ───────────────────────────────────────────────────────
    ar = result.get("automation_risk", {})
    if ar:
        story.append(_section_head("AI AUTOMATION RISK", S))
        level = ar.get("level", "moderate").upper()
        timeline = ar.get("timeline", "")
        col = score_color(ar.get("score", 50), "risk")
        story.append(Paragraph(
            f'<font color="{col.hexval()}"><b>✅ Risk Level: {level}</b></font>'
            + (f' · Timeline: {timeline}' if timeline else ''),
            sty("rl", fontSize=10, spaceAfter=6)
        ))
        tasks = ar.get("at_risk_tasks", [])
        if tasks:
            story.append(Paragraph("<b>AUTOMATION FRONTIER — Tasks with AI Assistance Potential</b>",
                                   sty("aft", fontSize=9, textColor=GOLD, spaceAfter=4)))
            story.append(Paragraph("   ".join(tasks),
                                   sty("tsk", fontSize=9, textColor=MID, spaceAfter=8)))

    # ── Human Edge ────────────────────────────────────────────────────────────
    human_edge = result.get("human_edge", [])
    if human_edge:
        story.append(Paragraph("<b>HUMAN EDGE — Tasks You Durably Own</b>",
                               sty("het", fontSize=9, textColor=GOLD, spaceAfter=4)))
        story.append(Paragraph("   ".join(human_edge),
                               sty("hev", fontSize=9, textColor=MID, spaceAfter=8)))

    # ── AI Tools ─────────────────────────────────────────────────────────────
    ai_replacing = result.get("ai_tools_replacing", [])
    ai_adopt     = result.get("ai_tools_to_adopt", [])
    if ai_replacing or ai_adopt:
        story.append(_section_head("AI SYSTEMS AFFECTING THIS ROLE", S))
        if ai_replacing:
            story.append(Paragraph("<b>Already assisting tasks in this role:</b>",
                                   sty("aih", fontSize=9, textColor=DARK, spaceAfter=4)))
            story.append(Paragraph("   ".join(ai_replacing),
                                   sty("ait", fontSize=9, textColor=MID, spaceAfter=6)))
        if ai_adopt:
            story.append(Paragraph("<b>Tools to actively use to amplify output:</b>",
                                   sty("ath", fontSize=9, textColor=DARK, spaceAfter=4)))
            story.append(Paragraph("   ".join(ai_adopt),
                                   sty("att", fontSize=9, textColor=TEAL, spaceAfter=8)))

    # ── Career Moat ───────────────────────────────────────────────────────────
    moat = result.get("career_moat", {})
    if moat:
        story.append(_section_head("STRATEGIC POSITION — YOUR CAREER MOAT", S))
        story.append(Paragraph(result.get("strategic_direction", ""),
                               sty("sd", fontSize=10, textColor=MID, spaceAfter=10, leading=15)))
        moat_data = [
            ("Core Moat",        moat.get("core_strength", "")),
            ("Primary Threat",   moat.get("the_threat", "")),
            ("Strategic Move",   moat.get("one_move", "")),
        ]
        for label, text in moat_data:
            if text:
                t = Table([[
                    Paragraph(f"<b>{label}</b>", sty("ml", fontSize=9, textColor=GOLD)),
                    Paragraph(text, sty("mv", fontSize=9, textColor=MID, leading=13))
                ]], colWidths=[35*mm, W-ML-MR-35*mm])
                t.setStyle(TableStyle([
                    ("BACKGROUND",    (0,0), (-1,-1), BEIGE),
                    ("LINEAFTER",     (0,0), (0,-1),  1, GOLD),
                    ("TOPPADDING",    (0,0), (-1,-1), 5),
                    ("BOTTOMPADDING", (0,0), (-1,-1), 5),
                    ("LEFTPADDING",   (0,0), (-1,-1), 8),
                    ("RIGHTPADDING",  (0,0), (-1,-1), 8),
                    ("VALIGN",        (0,0), (-1,-1), "TOP"),
                ]))
                story.append(t)
                story.append(Spacer(1, 3))
        story.append(Spacer(1, 6))

    # ── Upskilling Roadmap ────────────────────────────────────────────────────
    roadmap = result.get("upskilling_roadmap", [])
    if roadmap:
        story.append(_section_head("UPSKILLING ROADMAP — YOUR MOAT BUILDERS", S))
        for item in roadmap:
            pri   = item.get("priority", "medium").upper()
            col   = RED if pri == "HIGH" else (AMBER if pri == "MEDIUM" else GREEN)
            items = [
                [Paragraph(f'<font color="{col.hexval()}"><b>{pri}</b></font>',
                           sty("pb", fontSize=8, alignment=TA_CENTER)),
                 Paragraph(f'<b>{item.get("skill","")}</b>', sty("sk", fontSize=10, textColor=DARK))],
                [Paragraph(""),
                 Paragraph(f'<i>Why this matters:</i> {item.get("why","")}',
                           sty("sw", fontSize=9, textColor=MID, leading=13))],
                [Paragraph(""),
                 Paragraph(f'📚 {item.get("resources","")}',
                           sty("sr", fontSize=9, textColor=TEAL, leading=13))],
            ]
            t = Table(items, colWidths=[15*mm, W-ML-MR-15*mm])
            t.setStyle(TableStyle([
                ("LINEBELOW",     (0,0), (-1,-1), 0.3, BORDER),
                ("TOPPADDING",    (0,0), (-1,-1), 4),
                ("BOTTOMPADDING", (0,0), (-1,-1), 4),
                ("LEFTPADDING",   (0,0), (-1,-1), 4),
                ("VALIGN",        (0,0), (-1,-1), "TOP"),
                ("SPAN",          (0,1), (0,2)),
            ]))
            story.append(t)
        story.append(Spacer(1, 6))

    # ── CV Improvements ───────────────────────────────────────────────────────
    improvements = result.get("cv_improvements", [])
    if improvements:
        story.append(_section_head("CV IMPROVEMENT SUGGESTIONS", S))
        table_data = [
            [Paragraph("<b>PRIORITY</b>", sty("th", fontSize=8, textColor=LIGHT)),
             Paragraph("<b>ACTION</b>",   sty("th", fontSize=8, textColor=LIGHT))]
        ]
        for imp in improvements:
            pri = imp.get("priority", "medium").upper()
            col = RED if pri == "HIGH" else (AMBER if pri == "MEDIUM" else GREEN)
            table_data.append([
                Paragraph(f'<font color="{col.hexval()}"><b>{pri}</b></font>',
                          sty("ip", fontSize=8, alignment=TA_CENTER)),
                Paragraph(imp.get("action", ""), sty("ia", fontSize=9, textColor=MID, leading=13))
            ])
        t = Table(table_data, colWidths=[18*mm, W-ML-MR-18*mm])
        t.setStyle(TableStyle([
            ("BACKGROUND",    (0,0), (-1,0),  SECTION_BG),
            ("LINEBELOW",     (0,0), (-1,-1), 0.3, BORDER),
            ("TOPPADDING",    (0,0), (-1,-1), 5),
            ("BOTTOMPADDING", (0,0), (-1,-1), 5),
            ("LEFTPADDING",   (0,0), (-1,-1), 6),
            ("VALIGN",        (0,0), (-1,-1), "TOP"),
        ]))
        story.append(t)
        story.append(Spacer(1, 6))

    # ── 90-Day Action Plan ────────────────────────────────────────────────────
    action = result.get("action_plan", {})
    if action:
        story.append(_section_head("90-DAY WORKMOAT ACTION PLAN", S))
        phases = [
            ("Days 1–30 · Protect",  "Immediate defence — fix CV signal, deploy first AI workflows",
             action.get("days_1_30", [])),
            ("Days 31–60 · Build",   "Deepen AI fluency, begin formal credentials, integrate AI workflows",
             action.get("days_31_60", [])),
            ("Days 61–90 · Grow",    "Produce AI-powered proof of capability, complete credential, position for next role",
             action.get("days_61_90", [])),
        ]
        for phase_title, phase_sub, items in phases:
            story.append(Paragraph(phase_title, S["phase"]))
            story.append(Paragraph(phase_sub,   S["phasesub"]))
            for item in items:
                story.append(Paragraph(f"☐  {item}", S["action"]))
            story.append(Spacer(1, 6))

    # ── Footer ────────────────────────────────────────────────────────────────
    story.append(HRFlowable(width="100%", thickness=0.5, color=BORDER, spaceBefore=16))
    story.append(Paragraph(
        f"workmoat.ai · Confidential report for {name} · {today}",
        S["footer"]
    ))
    story.append(Paragraph(
        "WorkMoat — Know your moat. Defend your career.",
        sty("tag", fontSize=7, textColor=LIGHT, alignment=TA_CENTER)
    ))

    doc.build(story)


def _section_head(text, S):
    return Paragraph(f'<font color="{GOLD.hexval()}"><b>{text}</b></font>', S["sec"])

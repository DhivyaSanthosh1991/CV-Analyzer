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
BEIGE      = colors.HexColor("#F5F2EB")
DARK       = colors.HexColor("#2C2C2A")
MID        = colors.HexColor("#444441")
MUTED      = colors.HexColor("#888780")
BORDER     = colors.HexColor("#D3D1C7")
GREEN_BG   = colors.HexColor("#EAF3DE")
GREEN_TXT  = colors.HexColor("#3B6D11")
AMBER_BG   = colors.HexColor("#FAEEDA")
AMBER_TXT  = colors.HexColor("#854F0B")
RED_BG     = colors.HexColor("#FCEBEB")
RED_TXT    = colors.HexColor("#A32D2D")
BLUE_BG    = colors.HexColor("#E6F1FB")
BLUE_TXT   = colors.HexColor("#185FA5")
WHITE      = colors.white

W, H = A4
MARGIN = 18 * mm


def make_styles():
    base = getSampleStyleSheet()
    def s(name, **kw):
        return ParagraphStyle(name, **kw)

    return {
        "logo":      s("logo",   fontName="Helvetica",     fontSize=8,  textColor=MUTED,     spaceAfter=2,   letterSpacing=2),
        "h1":        s("h1",     fontName="Times-BoldItalic", fontSize=26, textColor=DARK,   spaceAfter=4,   leading=32),
        "h2":        s("h2",     fontName="Helvetica-Bold", fontSize=11, textColor=DARK,     spaceAfter=4,   spaceBefore=14),
        "h3":        s("h3",     fontName="Helvetica-Bold", fontSize=9,  textColor=MUTED,    spaceAfter=3,   spaceBefore=8,  letterSpacing=1),
        "body":      s("body",   fontName="Helvetica",     fontSize=9,  textColor=MID,      spaceAfter=4,   leading=14),
        "small":     s("small",  fontName="Helvetica",     fontSize=8,  textColor=MUTED,    spaceAfter=2,   leading=12),
        "chip":      s("chip",   fontName="Helvetica",     fontSize=8,  textColor=DARK,     spaceAfter=0),
        "score_num": s("score_num", fontName="Helvetica-Bold", fontSize=24, textColor=DARK, spaceAfter=0, alignment=TA_CENTER),
        "score_lbl": s("score_lbl", fontName="Helvetica",  fontSize=7,  textColor=MUTED,    spaceAfter=0, alignment=TA_CENTER),
        "center":    s("center", fontName="Helvetica",     fontSize=9,  textColor=MID,      spaceAfter=4, alignment=TA_CENTER),
        "roadmap_skill": s("rs", fontName="Helvetica-Bold",fontSize=9,  textColor=DARK,     spaceAfter=1),
        "roadmap_reason":s("rr", fontName="Helvetica",    fontSize=8,  textColor=MID,      spaceAfter=1,   leading=12),
        "roadmap_res":   s("rre",fontName="Helvetica",    fontSize=7,  textColor=MUTED,    spaceAfter=0),
    }


def score_color(score, invert=False):
    if invert:
        if score >= 70: return RED_TXT
        if score >= 40: return AMBER_TXT
        return GREEN_TXT
    if score >= 70: return GREEN_TXT
    if score >= 40: return AMBER_TXT
    return RED_TXT


def chip_style(kind="neutral"):
    if kind == "green": return (GREEN_BG, GREEN_TXT)
    if kind == "amber": return (AMBER_BG, AMBER_TXT)
    if kind == "red":   return (RED_BG,   RED_TXT)
    if kind == "blue":  return (BLUE_BG,  BLUE_TXT)
    return (colors.HexColor("#F0ECE2"), MUTED)


def chips_table(items, kind="neutral", cols=3):
    if not items: return None
    bg, tc = chip_style(kind)
    rows, row = [], []
    for i, item in enumerate(items):
        cell = Paragraph(str(item), ParagraphStyle("cc", fontName="Helvetica",
                         fontSize=7.5, textColor=tc, alignment=TA_CENTER))
        row.append(cell)
        if len(row) == cols or i == len(items) - 1:
            while len(row) < cols: row.append("")
            rows.append(row); row = []

    col_w = (W - 2 * MARGIN) / cols
    t = Table(rows, colWidths=[col_w] * cols, rowHeights=16)
    t.setStyle(TableStyle([
        ("BACKGROUND", (0,0), (-1,-1), bg),
        ("ROUNDEDCORNERS", [4]),
        ("LEFTPADDING",  (0,0), (-1,-1), 8),
        ("RIGHTPADDING", (0,0), (-1,-1), 8),
        ("TOPPADDING",   (0,0), (-1,-1), 3),
        ("BOTTOMPADDING",(0,0), (-1,-1), 3),
        ("GRID",         (0,0), (-1,-1), 0.3, BORDER),
    ]))
    return t


def score_card_row(scores_data):
    cells = []
    for label, value, color in scores_data:
        num_p  = Paragraph(str(value), ParagraphStyle("sn", fontName="Helvetica-Bold",
                           fontSize=22, textColor=color, alignment=TA_CENTER))
        lbl_p  = Paragraph(label,      ParagraphStyle("sl", fontName="Helvetica",
                           fontSize=7,  textColor=MUTED,  alignment=TA_CENTER))
        cells.append([num_p, lbl_p])

    n    = len(scores_data)
    col_w = (W - 2 * MARGIN) / n
    t = Table([[c[0] for c in cells], [c[1] for c in cells]],
              colWidths=[col_w] * n)
    t.setStyle(TableStyle([
        ("BACKGROUND",  (0,0), (-1,-1), BEIGE),
        ("ALIGN",       (0,0), (-1,-1), "CENTER"),
        ("TOPPADDING",  (0,0), (-1,-1), 10),
        ("BOTTOMPADDING",(0,0),(-1,-1), 10),
        ("GRID",        (0,0), (-1,-1), 0.3, BORDER),
    ]))
    return t


def bar_table(label, value, color):
    BAR_W = W - 2 * MARGIN - 90
    filled = int(BAR_W * value / 100)
    empty  = BAR_W - filled

    bar_data = [[
        Paragraph(label, ParagraphStyle("bl", fontName="Helvetica", fontSize=8, textColor=MUTED)),
        "",
        Paragraph(str(value), ParagraphStyle("bv", fontName="Helvetica-Bold", fontSize=8,
                               textColor=color, alignment=TA_RIGHT))
    ]]
    t = Table(bar_data, colWidths=[80, BAR_W, 28])
    t.setStyle(TableStyle([
        ("VALIGN",       (0,0),(-1,-1), "MIDDLE"),
        ("LEFTPADDING",  (0,0),(-1,-1), 0),
        ("RIGHTPADDING", (0,0),(-1,-1), 0),
        ("TOPPADDING",   (0,0),(-1,-1), 3),
        ("BOTTOMPADDING",(0,0),(-1,-1), 3),
    ]))
    return t


def section_header(text, st):
    return [
        Paragraph(text.upper(), st["h3"]),
        HRFlowable(width="100%", thickness=0.5, color=BORDER, spaceAfter=6)
    ]


def generate_report_pdf(data: dict, output_path: str):
    doc = SimpleDocTemplate(
        output_path, pagesize=A4,
        leftMargin=MARGIN, rightMargin=MARGIN,
        topMargin=MARGIN, bottomMargin=MARGIN
    )
    st    = make_styles()
    story = []

    # ── Cover header ─────────────────────────────────────────────────────────
    story.append(Paragraph("workmoat.ai", st["logo"]))
    story.append(Spacer(1, 6))
    story.append(Paragraph(
        f"{data.get('name','Professional')} — Full Report",
        st["h1"]
    ))
    story.append(Paragraph(
        f"{data.get('role','–')}   ·   Generated {datetime.now().strftime('%d %b %Y')}",
        st["small"]
    ))
    story.append(Spacer(1, 8))
    story.append(HRFlowable(width="100%", thickness=1, color=DARK, spaceAfter=10))

    # ── Score row ─────────────────────────────────────────────────────────────
    ov  = data.get("overall_score", 0)
    sus = data.get("ai_susceptibility_score", 0)
    aug = data.get("ai_augment_score", 0)
    jf  = (data.get("job_fit") or {}).get("score")
    scores = [
        ("CV quality", ov,  score_color(ov)),
        ("AI susceptibility", sus, score_color(sus, invert=True)),
        ("AI augment score",  aug, score_color(aug)),
    ]
    if jf is not None:
        scores.append(("Job fit", jf, score_color(jf)))
    story.append(score_card_row(scores))
    story.append(Spacer(1, 14))

    # ── CV Section scores ─────────────────────────────────────────────────────
    story += section_header("CV quality breakdown", st)
    cv_secs = data.get("cv_sections", {})
    labels  = {"contact_info":"Contact info","summary":"Summary",
                "experience":"Experience","skills":"Skills","formatting":"Formatting"}
    for key, label in labels.items():
        sec = cv_secs.get(key, {})
        sc  = sec.get("score", 0)
        story.append(bar_table(label, sc, score_color(sc)))
    story.append(Spacer(1, 6))

    # CV feedback table
    fb_rows = []
    for key, label in labels.items():
        sec = cv_secs.get(key, {})
        fb  = sec.get("feedback", "—")
        col = GREEN_TXT if sec.get("status") == "good" else (AMBER_TXT if sec.get("status") == "warn" else BLUE_TXT)
        fb_rows.append([
            Paragraph(label, ParagraphStyle("fl", fontName="Helvetica-Bold", fontSize=8, textColor=col)),
            Paragraph(fb,    ParagraphStyle("fb", fontName="Helvetica",      fontSize=8, textColor=MID, leading=12))
        ])
    t = Table(fb_rows, colWidths=[90, W - 2*MARGIN - 90])
    t.setStyle(TableStyle([
        ("VALIGN",       (0,0),(-1,-1),"TOP"),
        ("LEFTPADDING",  (0,0),(-1,-1), 4),
        ("RIGHTPADDING", (0,0),(-1,-1), 4),
        ("TOPPADDING",   (0,0),(-1,-1), 5),
        ("BOTTOMPADDING",(0,0),(-1,-1), 5),
        ("LINEBELOW",    (0,0),(-1,-2), 0.3, BORDER),
    ]))
    story.append(t)
    story.append(Spacer(1, 14))

    # ── Strengths ─────────────────────────────────────────────────────────────
    strengths = data.get("strengths", [])
    if strengths:
        story += section_header("Key strengths", st)
        ct = chips_table(strengths, "green", cols=4)
        if ct: story.append(ct)
        story.append(Spacer(1, 14))

    # ── AI Risk ───────────────────────────────────────────────────────────────
    story += section_header("AI automation risk", st)
    ar = data.get("automation_risk", {})
    risk_col = RED_TXT if ar.get("level")=="high" else (AMBER_TXT if ar.get("level")=="medium" else GREEN_TXT)
    risk_lbl = Paragraph(
        f"Risk level: <b>{(ar.get('level') or '—').upper()}</b>   ·   Timeline: {ar.get('timeline','—')}",
        ParagraphStyle("rl", fontName="Helvetica", fontSize=9, textColor=risk_col, spaceAfter=4)
    )
    story.append(risk_lbl)
    if ar.get("summary"):
        story.append(Paragraph(ar["summary"], st["body"]))
    story.append(Spacer(1, 8))

    rb = data.get("role_breakdown", {})
    if rb:
        story.append(Paragraph(f"Automatable tasks ({rb.get('automation_pct',0)}%)", st["h3"]))
        ct = chips_table(rb.get("automatable_tasks",[]), "red", cols=3)
        if ct: story.append(ct)
        story.append(Spacer(1, 6))
        story.append(Paragraph("Human-essential tasks", st["h3"]))
        ct = chips_table(rb.get("human_tasks",[]), "green", cols=3)
        if ct: story.append(ct)
    story.append(Spacer(1, 14))

    # ── AI Systems ────────────────────────────────────────────────────────────
    ai_sys = data.get("ai_systems", {})
    if ai_sys:
        story += section_header("AI systems affecting this role", st)
        if ai_sys.get("already_replacing"):
            story.append(Paragraph("Already replacing tasks", st["h3"]))
            ct = chips_table(ai_sys["already_replacing"], "red", cols=3)
            if ct: story.append(ct)
            story.append(Spacer(1, 6))
        if ai_sys.get("augmenting"):
            story.append(Paragraph("Augmenting (use these to your advantage)", st["h3"]))
            ct = chips_table(ai_sys["augmenting"], "blue", cols=3)
            if ct: story.append(ct)
        story.append(Spacer(1, 14))

    # ── Job fit ───────────────────────────────────────────────────────────────
    jf_data = data.get("job_fit", {})
    if jf_data and jf_data.get("score") is not None:
        story += section_header("Job fit analysis", st)
        if jf_data.get("matched_skills"):
            story.append(Paragraph("Matched skills", st["h3"]))
            ct = chips_table(jf_data["matched_skills"], "green", cols=4)
            if ct: story.append(ct)
            story.append(Spacer(1, 6))
        if jf_data.get("missing_skills"):
            story.append(Paragraph("Skill gaps", st["h3"]))
            ct = chips_table(jf_data["missing_skills"], "amber", cols=4)
            if ct: story.append(ct)
        story.append(Spacer(1, 14))

    # ── Strategic position ────────────────────────────────────────────────────
    sp = data.get("strategic_position")
    if sp:
        story += section_header("Strategic position — your career moat", st)
        story.append(Paragraph(sp, st["body"]))
        story.append(Spacer(1, 14))

    # ── Upskilling roadmap ────────────────────────────────────────────────────
    roadmap = data.get("upskilling_roadmap", [])
    if roadmap:
        story += section_header("Upskilling roadmap", st)
        for item in roadmap:
            p = item.get("priority","low")
            bg, tc = chip_style("red" if p=="high" else ("amber" if p=="medium" else "green"))
            priority_label = Paragraph(p.upper(),
                ParagraphStyle("pl", fontName="Helvetica-Bold", fontSize=7,
                               textColor=tc, alignment=TA_CENTER))
            skill_text = [
                Paragraph(item.get("skill",""), st["roadmap_skill"]),
                Paragraph(item.get("reason",""), st["roadmap_reason"]),
                Paragraph(f"Resources: {item.get('resources','–')}", st["roadmap_res"]),
            ]
            row = Table([[priority_label, skill_text]],
                        colWidths=[50, W - 2*MARGIN - 50])
            row.setStyle(TableStyle([
                ("VALIGN",       (0,0),(-1,-1),"TOP"),
                ("BACKGROUND",   (0,0),(0,0),   bg),
                ("LEFTPADDING",  (0,0),(-1,-1), 8),
                ("RIGHTPADDING", (0,0),(-1,-1), 8),
                ("TOPPADDING",   (0,0),(-1,-1), 8),
                ("BOTTOMPADDING",(0,0),(-1,-1), 8),
                ("LINEBELOW",    (0,0),(-1,-1), 0.3, BORDER),
            ]))
            story.append(row)
        story.append(Spacer(1, 14))

    # ── CV Improvements ───────────────────────────────────────────────────────
    improvements = data.get("top_improvements", [])
    if improvements:
        story += section_header("CV improvement suggestions", st)
        for item in improvements:
            p  = item.get("priority","low")
            bg, tc = chip_style("red" if p=="high" else ("amber" if p=="medium" else "green"))
            lbl = Paragraph(p.upper(),
                ParagraphStyle("il", fontName="Helvetica-Bold", fontSize=7,
                               textColor=tc, alignment=TA_CENTER))
            sug = Paragraph(item.get("suggestion",""), st["body"])
            row = Table([[lbl, sug]], colWidths=[50, W - 2*MARGIN - 50])
            row.setStyle(TableStyle([
                ("VALIGN",       (0,0),(-1,-1),"MIDDLE"),
                ("BACKGROUND",   (0,0),(0,0),   bg),
                ("LEFTPADDING",  (0,0),(-1,-1), 8),
                ("RIGHTPADDING", (0,0),(-1,-1), 8),
                ("TOPPADDING",   (0,0),(-1,-1), 7),
                ("BOTTOMPADDING",(0,0),(-1,-1), 7),
                ("LINEBELOW",    (0,0),(-1,-1), 0.3, BORDER),
            ]))
            story.append(row)
        story.append(Spacer(1, 14))

    # ── Footer ────────────────────────────────────────────────────────────────
    story.append(HRFlowable(width="100%", thickness=0.5, color=BORDER, spaceBefore=10, spaceAfter=6))
    story.append(Paragraph(
        f"workmoat.ai  ·  Confidential report for {data.get('name','–')}  ·  {datetime.now().strftime('%d %b %Y')}",
        ParagraphStyle("foot", fontName="Helvetica", fontSize=7, textColor=MUTED, alignment=TA_CENTER)
    ))

    doc.build(story)

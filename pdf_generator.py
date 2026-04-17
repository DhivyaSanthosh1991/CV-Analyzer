"""WorkMoat — Full Diagnostic Report PDF Generator (ReportLab)"""
from reportlab.lib.pagesizes import A4
from reportlab.lib.styles import getSampleStyleSheet, ParagraphStyle
from reportlab.lib.units import mm
from reportlab.lib import colors
from reportlab.platypus import (
    SimpleDocTemplate, Paragraph, Spacer, Table, TableStyle,
    HRFlowable, KeepTogether, ListFlowable, ListItem
)
from reportlab.lib.enums import TA_LEFT, TA_CENTER, TA_RIGHT
from datetime import datetime

# ── Colour palette ─────────────────────────────────────────────────────────
C = {
    "dark":   colors.HexColor("#2C2C2C"),
    "mid":    colors.HexColor("#555555"),
    "light":  colors.HexColor("#999999"),
    "border": colors.HexColor("#E8E0D5"),
    "bg":     colors.HexColor("#FAF7F3"),
    "bg2":    colors.HexColor("#F5F0E8"),
    "gold":   colors.HexColor("#8B6914"),
    "gold2":  colors.HexColor("#5C4A2A"),
    "green":  colors.HexColor("#27AE60"),
    "amber":  colors.HexColor("#D4AC0D"),
    "orange": colors.HexColor("#D35400"),
    "red":    colors.HexColor("#C0392B"),
    "teal":   colors.HexColor("#1e7f8a"),
    "white":  colors.white,
}

W, H = A4
ML = MR = 22 * mm
MT = MB = 20 * mm
CW = W - ML - MR   # content width


def score_color(score, kind="quality"):
    if kind in ("susceptibility", "risk"):
        if score >= 76: return C["red"]
        if score >= 56: return C["orange"]
        if score >= 31: return C["amber"]
        return C["green"]
    elif kind == "augment":
        if score >= 70: return C["green"]
        if score >= 40: return C["amber"]
        return C["red"]
    else:
        if score >= 70: return C["green"]
        if score >= 40: return C["amber"]
        return C["red"]


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


def p_style(name="", size=10, bold=False, italic=False,
            color="#2C2C2C", align=TA_LEFT, after=5, before=0,
            leading=None, left=0):
    fn = "Helvetica"
    if bold and italic: fn = "Helvetica-BoldOblique"
    elif bold:          fn = "Helvetica-Bold"
    elif italic:        fn = "Helvetica-Oblique"
    return ParagraphStyle(
        name or f"s{size}{fn}",
        fontSize=size, fontName=fn,
        textColor=colors.HexColor(color) if isinstance(color, str) else color,
        alignment=align, spaceAfter=after, spaceBefore=before,
        leading=leading or size * 1.45, leftIndent=left
    )


def section_head(text):
    return [
        Spacer(1, 4),
        Paragraph(
            f'<font color="#8B6914"><b>{text.upper()}</b></font>',
            p_style(size=8, bold=True, color="#8B6914", after=0)
        ),
        HRFlowable(width=CW, thickness=1, color=C["border"], spaceAfter=10),
    ]


def chip_para(items, color_hex="#5C4A2A", bg_hex="#FAF7F3", border_hex="#DDD8CC"):
    """Render list of items as inline chip-style spans in a single paragraph."""
    if not items:
        return []
    chips = "  ".join([
        f'<font color="{color_hex}"><b> {item} </b></font>'
        for item in items
    ])
    return [Paragraph(chips, p_style(size=9, after=8))]


def badge_cell(priority):
    """Return a coloured badge paragraph for a priority level."""
    p = priority.lower()
    if p == "high":
        bg, fg = C["red"], C["white"]
        label = "HIGH"
    elif p == "medium":
        bg, fg = C["orange"], C["white"]
        label = "MEDIUM"
    else:
        bg, fg = C["green"], C["white"]
        label = "LOW"
    t = Table([[Paragraph(f'<b>{label}</b>',
                          p_style(size=7, bold=True, color=fg, align=TA_CENTER))]],
              colWidths=[14 * mm])
    t.setStyle(TableStyle([
        ("BACKGROUND",     (0,0), (-1,-1), bg),
        ("ROUNDEDCORNERS", [3]),
        ("TOPPADDING",     (0,0), (-1,-1), 2),
        ("BOTTOMPADDING",  (0,0), (-1,-1), 2),
        ("LEFTPADDING",    (0,0), (-1,-1), 3),
        ("RIGHTPADDING",   (0,0), (-1,-1), 3),
    ]))
    return t


def generate_report_pdf(result, output_path):
    doc = SimpleDocTemplate(
        output_path, pagesize=A4,
        leftMargin=ML, rightMargin=MR,
        topMargin=MT, bottomMargin=MB,
        title=f"WorkMoat Report — {result.get('name','')}"
    )

    name  = result.get("name", "Professional")
    role  = result.get("role", "")
    today = datetime.now().strftime("%d %b %Y")
    ar    = result.get("automation_risk") or {}
    moat  = result.get("career_moat") or {}
    bd    = result.get("cv_breakdown") or {}
    act   = result.get("action_plan") or {}

    story = []

    # ── HEADER ────────────────────────────────────────────────────────────────
    story.append(Paragraph("workmoat.ai",
                            p_style(size=8, color="#AAAAAA", after=4)))
    story.append(Paragraph(f"{name} — Full Diagnostic Report",
                            p_style(size=20, bold=True, italic=True,
                                    color="#1a1a1a", after=4, leading=24)))
    story.append(Paragraph(f"{role}  ·  Generated {today}",
                            p_style(size=9.5, color="#999999", after=14)))
    story.append(HRFlowable(width=CW, thickness=0.5, color=C["border"], spaceAfter=14))

    # ── SCORE GRID ─────────────────────────────────────────────────────────────
    scores = [
        (result.get("overall_score", 0),           "CV quality",           "quality"),
        (result.get("ai_susceptibility_score", 0), "AI susceptibility",    "susceptibility"),
        (result.get("ai_augment_score", 0),        "AI augment potential", "augment"),
        (result.get("job_fit_score", 0),           "Job fit",              "quality"),
        (ar.get("score", 0),                       "AI automation risk",   "risk"),
    ]
    score_cells = []
    for val, lbl, kind in scores:
        col = score_color(val, kind)
        cell = [
            Paragraph(str(val), p_style(size=30, bold=True, color=col,
                                         align=TA_CENTER, after=2, leading=32)),
            Paragraph(lbl, p_style(size=7.5, color="#999999", align=TA_CENTER, after=0)),
        ]
        score_cells.append(cell)

    score_table = Table([score_cells], colWidths=[CW / 5] * 5)
    score_table.setStyle(TableStyle([
        ("BOX",           (0,0), (-1,-1), 0.5, C["border"]),
        ("INNERGRID",     (0,0), (-1,-1), 0.5, C["border"]),
        ("VALIGN",        (0,0), (-1,-1), "MIDDLE"),
        ("TOPPADDING",    (0,0), (-1,-1), 12),
        ("BOTTOMPADDING", (0,0), (-1,-1), 12),
    ]))
    story.append(score_table)
    story.append(Spacer(1, 16))

    # ── CV QUALITY BREAKDOWN ──────────────────────────────────────────────────
    story.extend(section_head("CV Quality Breakdown"))
    bd_items = [
        ("Contact & Visibility", bd.get("contact", 0)),
        ("Professional Summary", bd.get("summary", 0)),
        ("Experience & Impact",  bd.get("experience", 0)),
        ("Skills Relevance",     bd.get("skills", 0)),
        ("Formatting & ATS",     bd.get("formatting", 0)),
    ]
    for lbl, val in bd_items:
        col = score_color(val, "quality")
        bar_filled = int((val / 100) * (CW - 60 * mm))
        bar_filled = max(2, bar_filled)
        bar_empty  = int(CW - 60 * mm) - bar_filled

        row_data = [
            Paragraph(lbl, p_style(size=9, color="#2C2C2C")),
            Table(
                [[None, None]],
                colWidths=[bar_filled, bar_empty],
                rowHeights=[5]
            ),
            Paragraph(f'<font color="{col.hexval()}"><b>{val}</b></font>',
                      p_style(size=9.5, bold=True, color=col, align=TA_RIGHT)),
        ]
        bar_table = Table(
            [[None, None]],
            colWidths=[bar_filled, max(1, bar_empty)],
            rowHeights=[5]
        )
        bar_table.setStyle(TableStyle([
            ("BACKGROUND", (0,0), (0,-1), col),
            ("BACKGROUND", (1,0), (1,-1), C["bg2"]),
        ]))

        row = Table(
            [[Paragraph(lbl, p_style(size=9.5, color="#2C2C2C", after=0)),
              bar_table,
              Paragraph(f'<font color="{col.hexval()}"><b>{val}</b></font>',
                        p_style(size=10, bold=True, align=TA_RIGHT, after=0))]],
            colWidths=[55 * mm, CW - 55 * mm - 16 * mm, 16 * mm]
        )
        row.setStyle(TableStyle([
            ("LINEBELOW",     (0,0), (-1,-1), 0.3, C["border"]),
            ("TOPPADDING",    (0,0), (-1,-1), 5),
            ("BOTTOMPADDING", (0,0), (-1,-1), 5),
            ("VALIGN",        (0,0), (-1,-1), "MIDDLE"),
        ]))
        story.append(row)
    story.append(Spacer(1, 12))

    # ── KEY STRENGTHS ─────────────────────────────────────────────────────────
    strengths = result.get("strengths", [])
    if strengths:
        story.extend(section_head("Key Strengths"))
        chips = "    ".join([f'<font color="#5C4A2A"><b>{s}</b></font>' for s in strengths])
        story.append(Paragraph(chips, p_style(size=9, after=8)))

    # ── KEY GAPS ──────────────────────────────────────────────────────────────
    gaps = result.get("gaps", [])
    if gaps:
        story.extend(section_head("Key Gaps"))
        for g in gaps:
            story.append(Paragraph(f"• {g}", p_style(size=9.5, color="#555555",
                                                       left=8, after=3)))
        story.append(Spacer(1, 6))

    # ── AUTOMATION RISK ───────────────────────────────────────────────────────
    story.extend(section_head("AI Automation Risk"))
    risk_score = ar.get("score", 0)
    risk_level = ar.get("level", "moderate").upper()
    risk_tl    = ar.get("timeline", "")
    risk_col   = score_color(risk_score, "risk")

    risk_box_content = [
        Paragraph(
            f'<font color="{risk_col.hexval()}"><b>Risk Level: {risk_level}</b></font>'
            + (f'  ·  Timeline: {risk_tl}' if risk_tl else ''),
            p_style(size=10.5, after=4)
        )
    ]
    risk_box = Table([[risk_box_content]], colWidths=[CW])
    risk_box.setStyle(TableStyle([
        ("BACKGROUND",    (0,0), (-1,-1), C["bg"]),
        ("BOX",           (0,0), (-1,-1), 0.5, colors.HexColor("#E8D5A0")),
        ("TOPPADDING",    (0,0), (-1,-1), 8),
        ("BOTTOMPADDING", (0,0), (-1,-1), 8),
        ("LEFTPADDING",   (0,0), (-1,-1), 12),
    ]))
    story.append(risk_box)
    story.append(Spacer(1, 8))

    at_risk = ar.get("at_risk_tasks", [])
    if at_risk:
        story.append(Paragraph(
            '<font color="#5C4A2A"><b>AUTOMATION FRONTIER — Tasks with AI Assistance Potential</b></font>',
            p_style(size=8.5, after=4)
        ))
        chips = "    ".join([f'<font color="#C0392B">{t}</font>' for t in at_risk])
        story.append(Paragraph(chips, p_style(size=9, after=8)))

    human_edge = result.get("human_edge", [])
    if human_edge:
        story.append(Paragraph(
            '<font color="#1A7A45"><b>HUMAN EDGE — Tasks You Durably Own</b></font>',
            p_style(size=8.5, after=4)
        ))
        chips = "    ".join([f'<font color="#1A7A45">{h}</font>' for h in human_edge])
        story.append(Paragraph(chips, p_style(size=9, after=8)))

    # ── AI SYSTEMS ────────────────────────────────────────────────────────────
    ai_replacing = result.get("ai_tools_replacing", [])
    ai_adopt     = result.get("ai_tools_to_adopt", [])
    if ai_replacing or ai_adopt:
        story.extend(section_head("AI Systems Affecting This Role"))
        if ai_replacing:
            story.append(Paragraph(
                '<b>Already assisting tasks in this role:</b>',
                p_style(size=9, color="#555555", after=6)
            ))
            table_data = [[
                Paragraph('<b>TOOL / SYSTEM</b>',
                           p_style(size=7.5, color="#999999", after=0)),
                Paragraph('<b>WHAT IT ASSISTS</b>',
                           p_style(size=7.5, color="#999999", after=0)),
            ]]
            for tool in ai_replacing:
                parts = tool.split(" — ", 1) if " — " in tool else [tool, "Assisting tasks in this role"]
                table_data.append([
                    Paragraph(parts[0], p_style(size=9.5, bold=True, color="#5C4A2A", after=0)),
                    Paragraph(parts[1] if len(parts) > 1 else "", p_style(size=9.5, color="#555555", after=0)),
                ])
            t = Table(table_data, colWidths=[65 * mm, CW - 65 * mm])
            t.setStyle(TableStyle([
                ("BACKGROUND",    (0,0), (-1,0),  C["bg"]),
                ("LINEBELOW",     (0,0), (-1,-1), 0.3, C["border"]),
                ("TOPPADDING",    (0,0), (-1,-1), 6),
                ("BOTTOMPADDING", (0,0), (-1,-1), 6),
                ("LEFTPADDING",   (0,0), (-1,-1), 8),
                ("VALIGN",        (0,0), (-1,-1), "TOP"),
            ]))
            story.append(t)
            story.append(Spacer(1, 8))

        if ai_adopt:
            story.append(Paragraph(
                '<b>Tools to actively use to amplify output:</b>',
                p_style(size=9, color="#555555", after=5)
            ))
            chips = "    ".join([
                f'<font color="#1e7f8a"><b>{t}</b></font>' for t in ai_adopt
            ])
            story.append(Paragraph(chips, p_style(size=9, after=10)))

    # ── STRATEGIC POSITION / CAREER MOAT ─────────────────────────────────────
    story.extend(section_head("Strategic Position — Your Career Moat"))

    strat = result.get("strategic_direction", "")
    if strat:
        story.append(Paragraph(strat, p_style(size=10, color="#444444",
                                               leading=15, after=10)))

    moat_fields = [
        ("Core Moat",      moat.get("core_strength", "")),
        ("Primary Threat", moat.get("the_threat", "")),
        ("Strategic Move", moat.get("one_move", "")),
    ]
    for label, text in moat_fields:
        if not text:
            continue
        moat_row = Table(
            [[Paragraph(f'<b>{label}</b>', p_style(size=9, bold=True, color="#5C4A2A", after=0)),
              Paragraph(text, p_style(size=9.5, color="#444444", leading=14, after=0))]],
            colWidths=[30 * mm, CW - 30 * mm]
        )
        moat_row.setStyle(TableStyle([
            ("BACKGROUND",    (0,0), (-1,-1), C["bg"]),
            ("LINEAFTER",     (0,0), (0,-1),  1.5, C["gold"]),
            ("TOPPADDING",    (0,0), (-1,-1), 6),
            ("BOTTOMPADDING", (0,0), (-1,-1), 6),
            ("LEFTPADDING",   (0,0), (-1,-1), 10),
            ("VALIGN",        (0,0), (-1,-1), "TOP"),
        ]))
        story.append(moat_row)
        story.append(Spacer(1, 3))
    story.append(Spacer(1, 10))

    # ── UPSKILLING ROADMAP ────────────────────────────────────────────────────
    roadmap = result.get("upskilling_roadmap", [])
    if roadmap:
        story.extend(section_head("Upskilling Roadmap — Your Moat Builders"))
        for item in roadmap:
            pri  = item.get("priority", "medium").lower()
            col  = C["red"] if pri == "high" else (C["orange"] if pri == "medium" else C["green"])
            lbl  = pri.upper()

            # Badge + title row
            badge_p = Paragraph(
                f'<b>{lbl}</b>',
                p_style(size=8, bold=True, color=C["white"], align=TA_CENTER, after=0)
            )
            badge_t = Table([[badge_p]], colWidths=[16 * mm])
            badge_t.setStyle(TableStyle([
                ("BACKGROUND",    (0,0), (-1,-1), col),
                ("TOPPADDING",    (0,0), (-1,-1), 2),
                ("BOTTOMPADDING", (0,0), (-1,-1), 2),
                ("LEFTPADDING",   (0,0), (-1,-1), 2),
                ("RIGHTPADDING",  (0,0), (-1,-1), 2),
            ]))
            title_p = Paragraph(
                f'<b>{item.get("skill","")}</b>',
                p_style(size=10.5, bold=True, color="#1a1a1a", after=0)
            )
            header = Table(
                [[badge_t, title_p]],
                colWidths=[18 * mm, CW - 18 * mm]
            )
            header.setStyle(TableStyle([
                ("VALIGN",     (0,0), (-1,-1), "MIDDLE"),
                ("LEFTPADDING",(0,0), (-1,-1), 0),
            ]))

            why_p = Paragraph(
                f'<i>Why this matters for you:</i> {item.get("why","")}',
                p_style(size=9.5, color="#555555", leading=14, after=3)
            )
            res_p = Paragraph(
                f'📚 {item.get("resources","")}',
                p_style(size=9.5, color="#1e7f8a", leading=13, after=0)
            )

            left_col = pri.upper()[0]   # H / M / L for left border color
            container = Table(
                [[header], [why_p], [res_p]],
                colWidths=[CW]
            )
            border_col = col
            container.setStyle(TableStyle([
                ("BOX",           (0,0), (-1,-1), 0.3, C["border"]),
                ("LINEBEFORE",    (0,0), (0,-1),  3,   border_col),
                ("TOPPADDING",    (0,0), (-1,-1), 8),
                ("BOTTOMPADDING", (0,0), (-1,-1), 8),
                ("LEFTPADDING",   (0,0), (-1,-1), 10),
                ("RIGHTPADDING",  (0,0), (-1,-1), 10),
            ]))
            story.append(container)
            story.append(Spacer(1, 5))
        story.append(Spacer(1, 8))

    # ── CV IMPROVEMENTS ───────────────────────────────────────────────────────
    improvements = result.get("cv_improvements", [])
    if improvements:
        story.extend(section_head("CV Improvement Suggestions"))
        table_data = [[
            Paragraph('<b>PRIORITY</b>', p_style(size=7.5, color="#999999", align=TA_CENTER, after=0)),
            Paragraph('<b>ACTION</b>',   p_style(size=7.5, color="#999999", after=0)),
        ]]
        for imp in improvements:
            pri   = imp.get("priority", "medium")
            col   = C["red"] if pri == "high" else (C["orange"] if pri == "medium" else C["green"])
            badge_p = Paragraph(
                f'<b>{pri.upper()}</b>',
                p_style(size=8, bold=True, color=C["white"], align=TA_CENTER, after=0)
            )
            bt = Table([[badge_p]], colWidths=[16 * mm])
            bt.setStyle(TableStyle([
                ("BACKGROUND",    (0,0), (-1,-1), col),
                ("TOPPADDING",    (0,0), (-1,-1), 2),
                ("BOTTOMPADDING", (0,0), (-1,-1), 2),
            ]))
            table_data.append([
                bt,
                Paragraph(imp.get("action",""), p_style(size=9.5, color="#444444",
                                                          leading=14, after=0)),
            ])
        t = Table(table_data, colWidths=[20 * mm, CW - 20 * mm])
        t.setStyle(TableStyle([
            ("BACKGROUND",    (0,0), (-1,0),  C["bg"]),
            ("LINEBELOW",     (0,0), (-1,-1), 0.3, C["border"]),
            ("TOPPADDING",    (0,0), (-1,-1), 7),
            ("BOTTOMPADDING", (0,0), (-1,-1), 7),
            ("LEFTPADDING",   (0,0), (-1,-1), 8),
            ("VALIGN",        (0,0), (-1,-1), "MIDDLE"),
        ]))
        story.append(t)
        story.append(Spacer(1, 12))

    # ── 90-DAY ACTION PLAN ────────────────────────────────────────────────────
    if act:
        story.extend(section_head("90-Day WorkMoat Action Plan"))
        phases = [
            ("Days 1–30 · Protect",
             "Immediate defence — fix CV signal, deploy first AI workflows, establish AI literacy baseline",
             act.get("days_1_30", [])),
            ("Days 31–60 · Build",
             "Deepen AI fluency, begin formal credentials, integrate AI into core workflows",
             act.get("days_31_60", [])),
            ("Days 61–90 · Grow",
             "Produce AI-powered proof of capability, complete credential, position for next role",
             act.get("days_61_90", [])),
        ]
        for phase_title, phase_sub, items in phases:
            if not items:
                continue
            phase_block = []
            phase_block.append(Paragraph(
                phase_title,
                p_style(size=11, bold=True, color="#1a1a1a", after=2, before=2)
            ))
            phase_block.append(Paragraph(
                phase_sub,
                p_style(size=8.5, italic=True, color="#999999", after=8)
            ))
            for item in items:
                phase_block.append(Paragraph(
                    f'<font color="#8B6914"><b>☐</b></font>  {item}',
                    p_style(size=9.5, color="#444444", leading=14, after=5, left=6)
                ))

            container = Table([[phase_block]], colWidths=[CW])
            container.setStyle(TableStyle([
                ("BACKGROUND",    (0,0), (-1,-1), colors.HexColor("#FAFAF8")),
                ("BOX",           (0,0), (-1,-1), 0.3, C["border"]),
                ("TOPPADDING",    (0,0), (-1,-1), 10),
                ("BOTTOMPADDING", (0,0), (-1,-1), 10),
                ("LEFTPADDING",   (0,0), (-1,-1), 12),
                ("RIGHTPADDING",  (0,0), (-1,-1), 12),
            ]))
            story.append(container)
            story.append(Spacer(1, 6))
        story.append(Spacer(1, 8))

    # ── FOOTER ────────────────────────────────────────────────────────────────
    story.append(HRFlowable(width=CW, thickness=0.5, color=C["border"], spaceBefore=8))
    story.append(Paragraph(
        f"workmoat.ai  ·  Confidential report for {name}  ·  {today}",
        p_style(size=8, color="#CCCCCC", align=TA_CENTER, after=3)
    ))
    story.append(Paragraph(
        "WorkMoat — Know your moat. Defend your career.",
        p_style(size=7.5, color="#DDDDDD", align=TA_CENTER, after=0)
    ))

    doc.build(story)

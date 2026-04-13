import os
import base64
from sendgrid import SendGridAPIClient
from sendgrid.helpers.mail import (
    Mail, Attachment, FileContent, FileName,
    FileType, Disposition, ContentId, To
)

SENDGRID_API_KEY  = os.getenv("SENDGRID_API_KEY", "YOUR_SENDGRID_API_KEY")
FROM_EMAIL        = os.getenv("FROM_EMAIL",        "reports@workmoat.ai")
FROM_NAME         = "WorkMoat"


def _build_html(name: str, role: str, scores: dict) -> str:
    ov  = scores.get("overall_score", 0)
    sus = scores.get("ai_susceptibility_score", 0)
    aug = scores.get("ai_augment_score", 0)

    def score_color(v, invert=False):
        if invert:
            return "#A32D2D" if v >= 70 else ("#854F0B" if v >= 40 else "#3B6D11")
        return "#3B6D11" if v >= 70 else ("#854F0B" if v >= 40 else "#A32D2D")

    risk = scores.get("automation_risk", {})
    risk_level = (risk.get("level") or "unknown").capitalize()
    risk_col   = "#A32D2D" if risk.get("level") == "high" else ("#854F0B" if risk.get("level") == "medium" else "#3B6D11")

    upskill_rows = ""
    for item in (scores.get("upskilling_roadmap") or [])[:3]:
        p   = item.get("priority", "low")
        bg  = "#FCEBEB" if p == "high" else ("#FAEEDA" if p == "medium" else "#EAF3DE")
        tc  = "#A32D2D" if p == "high" else ("#854F0B" if p == "medium" else "#3B6D11")
        upskill_rows += f"""
        <tr>
          <td style="padding:10px 12px;border-bottom:1px solid #EDE9DF;vertical-align:top;width:70px">
            <span style="background:{bg};color:{tc};font-size:10px;font-weight:600;padding:2px 8px;border-radius:100px;text-transform:uppercase;letter-spacing:0.05em">{p}</span>
          </td>
          <td style="padding:10px 12px;border-bottom:1px solid #EDE9DF;vertical-align:top">
            <div style="font-size:13px;font-weight:600;color:#2C2C2A;margin-bottom:2px">{item.get('skill','')}</div>
            <div style="font-size:12px;color:#888780;line-height:1.5">{item.get('reason','')}</div>
          </td>
        </tr>"""

    improvements = ""
    for item in (scores.get("top_improvements") or [])[:3]:
        p  = item.get("priority", "low")
        tc = "#A32D2D" if p == "high" else ("#854F0B" if p == "medium" else "#3B6D11")
        improvements += f"""
        <li style="margin-bottom:10px;color:#444441;font-size:13px;line-height:1.6">
          <span style="color:{tc};font-weight:600;text-transform:capitalize">[{p}]</span> {item.get('suggestion','')}
        </li>"""

    return f"""
<!DOCTYPE html>
<html lang="en">
<head><meta charset="UTF-8"><meta name="viewport" content="width=device-width,initial-scale=1"></head>
<body style="margin:0;padding:0;background:#F5F2EB;font-family:'DM Sans',Helvetica,Arial,sans-serif">
<table width="100%" cellpadding="0" cellspacing="0" style="background:#F5F2EB;padding:32px 16px">
  <tr><td align="center">
    <table width="600" cellpadding="0" cellspacing="0" style="max-width:600px;width:100%">

      <!-- HEADER -->
      <tr>
        <td style="background:#2C2C2A;border-radius:14px 14px 0 0;padding:28px 36px;text-align:center">
          <div style="font-size:11px;font-weight:500;letter-spacing:0.15em;color:#888780;text-transform:lowercase;margin-bottom:12px">workmoat.ai</div>
          <div style="font-family:Georgia,'Times New Roman',serif;font-size:26px;font-style:italic;color:#F5F2EB;font-weight:400;line-height:1.3">
            Your full report is ready,<br>{name.split()[0] if name and name != 'Professional' else 'there'}.
          </div>
          <div style="font-size:13px;color:#888780;margin-top:8px">{role}</div>
        </td>
      </tr>

      <!-- SCORES -->
      <tr>
        <td style="background:#faf8f3;padding:24px 36px;border-left:1px solid #EDE9DF;border-right:1px solid #EDE9DF">
          <table width="100%" cellpadding="0" cellspacing="0">
            <tr>
              <td align="center" style="padding:12px 8px;background:#F5F2EB;border-radius:10px;border:1px solid #EDE9DF">
                <div style="font-size:28px;font-weight:500;color:{score_color(ov)}">{ov}</div>
                <div style="font-size:10px;color:#888780;margin-top:3px">CV quality</div>
              </td>
              <td width="10"></td>
              <td align="center" style="padding:12px 8px;background:#F5F2EB;border-radius:10px;border:1px solid #EDE9DF">
                <div style="font-size:28px;font-weight:500;color:{score_color(sus, True)}">{sus}</div>
                <div style="font-size:10px;color:#888780;margin-top:3px">AI susceptibility</div>
              </td>
              <td width="10"></td>
              <td align="center" style="padding:12px 8px;background:#F5F2EB;border-radius:10px;border:1px solid #EDE9DF">
                <div style="font-size:28px;font-weight:500;color:{score_color(aug)}">{aug}</div>
                <div style="font-size:10px;color:#888780;margin-top:3px">AI augment score</div>
              </td>
            </tr>
          </table>
        </td>
      </tr>

      <!-- RISK BANNER -->
      <tr>
        <td style="background:#faf8f3;padding:0 36px 20px;border-left:1px solid #EDE9DF;border-right:1px solid #EDE9DF">
          <div style="background:#F5F2EB;border:1px solid #EDE9DF;border-radius:10px;padding:14px 18px;display:flex">
            <span style="font-size:13px;color:#888780">Automation risk: </span>
            <span style="font-size:13px;font-weight:600;color:{risk_col};margin-left:6px">{risk_level}</span>
            <span style="font-size:12px;color:#888780;margin-left:12px">· {risk.get('timeline','–')}</span>
          </div>
        </td>
      </tr>

      <!-- UPSKILLING -->
      <tr>
        <td style="background:#faf8f3;padding:0 36px 20px;border-left:1px solid #EDE9DF;border-right:1px solid #EDE9DF">
          <div style="font-size:10px;font-weight:600;color:#888780;text-transform:uppercase;letter-spacing:0.08em;margin-bottom:10px">Upskilling roadmap</div>
          <table width="100%" cellpadding="0" cellspacing="0" style="border:1px solid #EDE9DF;border-radius:10px;overflow:hidden">
            {upskill_rows}
          </table>
        </td>
      </tr>

      <!-- IMPROVEMENTS -->
      <tr>
        <td style="background:#faf8f3;padding:0 36px 24px;border-left:1px solid #EDE9DF;border-right:1px solid #EDE9DF">
          <div style="font-size:10px;font-weight:600;color:#888780;text-transform:uppercase;letter-spacing:0.08em;margin-bottom:10px">CV improvements</div>
          <ul style="margin:0;padding-left:18px">
            {improvements}
          </ul>
        </td>
      </tr>

      <!-- CTA -->
      <tr>
        <td style="background:#faf8f3;padding:0 36px 32px;border-left:1px solid #EDE9DF;border-right:1px solid #EDE9DF;text-align:center">
          <div style="background:#EAF3DE;border-radius:10px;padding:16px 20px;margin-bottom:16px">
            <div style="font-size:13px;color:#3B6D11;font-weight:500;margin-bottom:4px">Your full PDF report is attached</div>
            <div style="font-size:12px;color:#3B6D11;opacity:0.8">All 7 sections including strategic position, AI systems, and complete roadmap</div>
          </div>
          <div style="font-size:11px;color:#888780;line-height:1.6">
            Keep this report safe — it's personalised to your CV and role.<br>
            If you have questions, reply to this email.
          </div>
        </td>
      </tr>

      <!-- FOOTER -->
      <tr>
        <td style="background:#2C2C2A;border-radius:0 0 14px 14px;padding:20px 36px;text-align:center">
          <div style="font-size:10px;color:#888780;letter-spacing:0.1em;text-transform:lowercase">workmoat.ai</div>
          <div style="font-size:10px;color:#5F5E5A;margin-top:6px">
            You're receiving this because you purchased a WorkMoat report.
          </div>
        </td>
      </tr>

    </table>
  </td></tr>
</table>
</body>
</html>"""


def send_report_email(to_email: str, name: str, role: str,
                       scores: dict, pdf_path: str) -> tuple[bool, str]:
    """
    Send the full report PDF to the user via email.
    Returns (success: bool, message: str)
    """
    try:
        html_content = _build_html(name, role, scores)

        display_name = name if name and name != "Professional" else "there"
        first_name   = display_name.split()[0]

        message = Mail(
            from_email=(FROM_EMAIL, FROM_NAME),
            to_emails=To(to_email),
            subject=f"Your WorkMoat Report — {role}",
            html_content=html_content
        )

        message.plain_text_content = (
            f"Hi {first_name},\n\n"
            f"Your WorkMoat full report is attached as a PDF.\n\n"
            f"CV Quality Score:      {scores.get('overall_score', 0)}/100\n"
            f"AI Susceptibility:     {scores.get('ai_susceptibility_score', 0)}/100\n"
            f"AI Augment Score:      {scores.get('ai_augment_score', 0)}/100\n\n"
            f"Your full report includes your strategic position, upskilling roadmap, "
            f"AI systems analysis, and CV improvements.\n\n"
            f"— WorkMoat Team\nworkmoat.ai"
        )

        # Attach PDF
        with open(pdf_path, "rb") as f:
            pdf_data = base64.b64encode(f.read()).decode()

        safe_name = (name or "report").replace(" ", "_")
        attachment = Attachment(
            FileContent(pdf_data),
            FileName(f"WorkMoat_Report_{safe_name}.pdf"),
            FileType("application/pdf"),
            Disposition("attachment"),
            ContentId("WorkMoatReport")
        )
        message.attachment = attachment

        sg = SendGridAPIClient(SENDGRID_API_KEY)
        response = sg.send(message)

        if response.status_code in (200, 202):
            return True, "Email sent successfully"
        else:
            return False, f"SendGrid returned status {response.status_code}"

    except Exception as e:
        return False, str(e)

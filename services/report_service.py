"""PDF Report Generation Service for Smart Deadline Rescue Agent using ReportLab."""
import io
import datetime
from typing import Dict, Any, List

from reportlab.lib.pagesizes import letter
from reportlab.lib import colors
from reportlab.platypus import (
    SimpleDocTemplate, Paragraph, Spacer, Table, TableStyle, KeepTogether, PageBreak, HRFlowable
)
from reportlab.lib.styles import getSampleStyleSheet, ParagraphStyle
from reportlab.lib.units import inch


class NumberedCanvas:
    """Canvas that records pages for drawing page numbers and running header/footer."""
    def __init__(self, *args, **kwargs):
        from reportlab.pdfgen import canvas
        self._canvas_class = canvas.Canvas

    # We will use onFirstPage and onLaterPages callback or canvas wrapper.


def create_pdf_report(state: Dict[str, Any]) -> bytes:
    """Generates a professional PDF recovery plan report from the agent state."""
    buffer = io.BytesIO()
    doc = SimpleDocTemplate(
        buffer,
        pagesize=letter,
        rightMargin=36,
        leftMargin=36,
        topMargin=40,
        bottomMargin=40,
    )

    styles = getSampleStyleSheet()

    # Custom styles
    primary_color = colors.HexColor("#4338ca")  # Indigo 700
    accent_color = colors.HexColor("#6366f1")   # Indigo 500
    text_dark = colors.HexColor("#0f172a")       # Slate 900
    text_muted = colors.HexColor("#64748b")      # Slate 500
    bg_light = colors.HexColor("#f8fafc")        # Slate 50
    border_color = colors.HexColor("#e2e8f0")

    title_style = ParagraphStyle(
        "DocTitle",
        parent=styles["Normal"],
        fontName="Helvetica-Bold",
        fontSize=20,
        leading=24,
        textColor=primary_color,
    )

    subtitle_style = ParagraphStyle(
        "DocSubtitle",
        parent=styles["Normal"],
        fontName="Helvetica",
        fontSize=10,
        leading=13,
        textColor=text_muted,
    )

    heading2_style = ParagraphStyle(
        "Heading2",
        parent=styles["Normal"],
        fontName="Helvetica-Bold",
        fontSize=13,
        leading=16,
        textColor=primary_color,
        spaceBefore=12,
        spaceAfter=6,
    )

    body_style = ParagraphStyle(
        "BodyDark",
        parent=styles["Normal"],
        fontName="Helvetica",
        fontSize=9,
        leading=12,
        textColor=text_dark,
    )

    table_header_style = ParagraphStyle(
        "TableHeader",
        parent=styles["Normal"],
        fontName="Helvetica-Bold",
        fontSize=8.5,
        leading=11,
        textColor=colors.white,
    )

    table_cell_style = ParagraphStyle(
        "TableCell",
        parent=styles["Normal"],
        fontName="Helvetica",
        fontSize=8,
        leading=10.5,
        textColor=text_dark,
    )

    badge_feasible = colors.HexColor("#16a34a")
    badge_infeasible = colors.HexColor("#dc2626")
    badge_optimized = colors.HexColor("#2563eb")

    story = []

    # 1. Header & Title
    session_id = state.get("session_id", "N/A")
    plan_status = state.get("plan_status", "FEASIBLE")
    generated_at = datetime.datetime.now().strftime("%B %d, %Y at %I:%M %p")

    story.append(Paragraph("Smart Deadline Rescue Agent", title_style))
    story.append(Paragraph("Personalized Academic Recovery Schedule & Deadline Feasibility Analysis", subtitle_style))
    story.append(Spacer(1, 8))
    story.append(HRFlowable(width="100%", thickness=1.5, color=primary_color, spaceBefore=2, spaceAfter=10))

    # 2. Executive Metadata Box
    status_bg = badge_feasible if plan_status == "FEASIBLE" else (badge_optimized if plan_status == "OPTIMIZED" else badge_infeasible)
    
    meta_data = [
        [
            Paragraph(f"<b>Session ID:</b> {session_id}", body_style),
            Paragraph(f"<b>Generated:</b> {generated_at}", body_style),
        ],
        [
            Paragraph(f"<b>Plan Status:</b> <font color='{status_bg.hexval()}'><b>{plan_status}</b></font>", body_style),
            Paragraph(f"<b>Optimization Cycles:</b> {state.get('optimization_attempts', 0)} / 3", body_style),
        ],
        [
            Paragraph(f"<b>Daily Study Capacity:</b> {state.get('available_time_per_day', 4.0)} hrs/day", body_style),
            Paragraph(f"<b>Total Pending Work:</b> {state.get('remaining_work', 0.0)} hrs", body_style),
        ],
    ]
    meta_table = Table(meta_data, colWidths=[270, 270])
    meta_table.setStyle(TableStyle([
        ('BACKGROUND', (0, 0), (-1, -1), bg_light),
        ('BOX', (0, 0), (-1, -1), 1, border_color),
        ('INNERGRID', (0, 0), (-1, -1), 0.5, border_color),
        ('TOPPADDING', (0, 0), (-1, -1), 5),
        ('BOTTOMPADDING', (0, 0), (-1, -1), 5),
        ('LEFTPADDING', (0, 0), (-1, -1), 8),
        ('RIGHTPADDING', (0, 0), (-1, -1), 8),
    ]))
    story.append(meta_table)
    story.append(Spacer(1, 10))

    # 3. Executive AI / Deterministic Summary
    final_report = state.get("final_report", {})
    source_tag = final_report.get("source", "deterministic_engine").upper()
    exec_summary_text = final_report.get("executive_summary", "Schedule generated successfully.")

    summary_box_data = [[
        Paragraph(f"<b>AGENT EXECUTIVE INSIGHT ({source_tag})</b><br/><br/>{exec_summary_text}", body_style)
    ]]
    summary_box = Table(summary_box_data, colWidths=[540])
    summary_box.setStyle(TableStyle([
        ('BACKGROUND', (0, 0), (-1, -1), colors.HexColor("#eef2ff")),
        ('BOX', (0, 0), (-1, -1), 1, accent_color),
        ('TOPPADDING', (0, 0), (-1, -1), 8),
        ('BOTTOMPADDING', (0, 0), (-1, -1), 8),
        ('LEFTPADDING', (0, 0), (-1, -1), 10),
        ('RIGHTPADDING', (0, 0), (-1, -1), 10),
    ]))
    story.append(summary_box)
    story.append(Spacer(1, 10))

    # 4. Tasks and Risk Summary Table
    story.append(Paragraph("1. Task Portfolio & Deadline Risk Breakdown", heading2_style))
    tasks = state.get("tasks", [])
    risks = state.get("deadline_risks", {})
    priorities = state.get("priority_scores", {})

    task_table_data = [
        [
            Paragraph("Rank", table_header_style),
            Paragraph("Task Name", table_header_style),
            Paragraph("Category", table_header_style),
            Paragraph("Deadline", table_header_style),
            Paragraph("Rem. Hours", table_header_style),
            Paragraph("Risk Level", table_header_style),
            Paragraph("Score (0-100)", table_header_style),
        ]
    ]

    for t in sorted(tasks, key=lambda x: priorities.get(str(x.get("id")), {}).get("rank", 999)):
        t_id = str(t.get("id"))
        p = priorities.get(t_id, {})
        r = risks.get(t_id, {})
        r_level = r.get("risk_level", "LOW")

        r_color = "#dc2626" if r_level == "CRITICAL" else ("#ea580c" if r_level == "HIGH" else ("#ca8a04" if r_level == "MODERATE" else "#16a34a"))
        
        tot_hrs = float(t.get("estimated_total_hours", 1.0))
        pct = float(t.get("completion_percentage", 0.0))
        rem = round(tot_hrs * (1.0 - (pct / 100.0)), 1)
        if t.get("completed", False):
            rem = 0.0

        task_table_data.append([
            Paragraph(f"#{p.get('rank', '-')}", table_cell_style),
            Paragraph(f"<b>{t.get('name', 'Untitled')}</b>", table_cell_style),
            Paragraph(str(t.get("category", "General")), table_cell_style),
            Paragraph(str(t.get("deadline", "-")), table_cell_style),
            Paragraph(f"{rem}h", table_cell_style),
            Paragraph(f"<font color='{r_color}'><b>{r_level}</b></font>", table_cell_style),
            Paragraph(f"<b>{p.get('score', 0.0)}</b>", table_cell_style),
        ])

    task_table = Table(task_table_data, colWidths=[35, 150, 75, 70, 60, 75, 75])
    task_table.setStyle(TableStyle([
        ('BACKGROUND', (0, 0), (-1, 0), primary_color),
        ('BOX', (0, 0), (-1, -1), 1, border_color),
        ('INNERGRID', (0, 0), (-1, -1), 0.5, border_color),
        ('TOPPADDING', (0, 0), (-1, -1), 4),
        ('BOTTOMPADDING', (0, 0), (-1, -1), 4),
        ('LEFTPADDING', (0, 0), (-1, -1), 5),
        ('RIGHTPADDING', (0, 0), (-1, -1), 5),
    ]))
    story.append(task_table)
    story.append(Spacer(1, 10))

    # 5. Daily Recovery Schedule Table
    story.append(Paragraph("2. Date-Wise Daily Recovery Schedule", heading2_style))
    daily_schedule = state.get("daily_schedule", [])

    if not daily_schedule:
        story.append(Paragraph("No study sessions scheduled (all tasks may be completed).", body_style))
    else:
        sched_table_data = [
            [
                Paragraph("Date", table_header_style),
                Paragraph("Day", table_header_style),
                Paragraph("Cap. / Allocated", table_header_style),
                Paragraph("Study Sessions (Start - End | Task | Duration)", table_header_style),
            ]
        ]

        for day in daily_schedule:
            d_date = day.get("date", "")
            d_name = day.get("day_name", "")
            cap = day.get("capacity_hours", 0.0)
            alloc = day.get("allocated_hours", 0.0)
            sessions = day.get("sessions", [])

            if day.get("is_busy"):
                sess_text = "<i>Unavailable / Busy Day (0h allocated)</i>"
            elif day.get("is_weekend") and not state.get("preferences", {}).get("include_weekends", True):
                sess_text = "<i>Weekend Study Disabled (0h allocated)</i>"
            elif not sessions:
                sess_text = "<i>No study sessions needed</i>"
            else:
                sess_lines = []
                for s in sessions:
                    badge = f" <font color='#dc2626'>[OVERDUE RESCUE]</font>" if s.get("is_after_deadline") else ""
                    sess_lines.append(
                        f"• <b>{s.get('start_time')} - {s.get('end_time')}</b>: {s.get('task_name')} ({s.get('duration_hours')}h){badge}"
                    )
                sess_text = "<br/>".join(sess_lines)

            sched_table_data.append([
                Paragraph(f"<b>{d_date}</b>", table_cell_style),
                Paragraph(d_name, table_cell_style),
                Paragraph(f"{alloc}h / {cap}h", table_cell_style),
                Paragraph(sess_text, table_cell_style),
            ])

        sched_table = Table(sched_table_data, colWidths=[75, 65, 80, 320])
        sched_table.setStyle(TableStyle([
            ('BACKGROUND', (0, 0), (-1, 0), primary_color),
            ('BOX', (0, 0), (-1, -1), 1, border_color),
            ('INNERGRID', (0, 0), (-1, -1), 0.5, border_color),
            ('TOPPADDING', (0, 0), (-1, -1), 4),
            ('BOTTOMPADDING', (0, 0), (-1, -1), 4),
            ('LEFTPADDING', (0, 0), (-1, -1), 5),
            ('RIGHTPADDING', (0, 0), (-1, -1), 5),
        ]))
        story.append(sched_table)

    story.append(Spacer(1, 10))

    # 6. Conflicts & Feasibility Alerts
    conflicts = state.get("conflicts", [])
    if conflicts:
        story.append(Paragraph("3. Detected Deadline Conflicts & Overloads", heading2_style))
        conflict_items = []
        for c in conflicts[:6]:
            sev = c.get("severity", "CRITICAL")
            c_color = "#dc2626" if sev == "CRITICAL" else "#ea580c"
            conflict_items.append(
                Paragraph(f"• <font color='{c_color}'><b>[{sev}]</b></font> {c.get('message')}", body_style)
            )
            conflict_items.append(Spacer(1, 3))
        story.append(KeepTogether(conflict_items))
        story.append(Spacer(1, 8))

    # 7. Recommendations Checklist
    recs = state.get("recommendations", [])
    if recs:
        story.append(Paragraph("4. Actionable Recovery Recommendations", heading2_style))
        rec_items = []
        for r in recs:
            rec_items.append(Paragraph(f"• [ ] {r}", body_style))
            rec_items.append(Spacer(1, 3))
        story.append(KeepTogether(rec_items))

    # Footer note
    story.append(Spacer(1, 15))
    story.append(HRFlowable(width="100%", thickness=0.5, color=border_color, spaceBefore=4, spaceAfter=6))
    story.append(Paragraph(
        "Generated autonomously by Geetha's Smart Deadline Rescue Agent — Built with LangGraph, Google Gemini, and FastAPI.",
        subtitle_style
    ))

    doc.build(story)
    pdf_bytes = buffer.getvalue()
    buffer.close()
    return pdf_bytes

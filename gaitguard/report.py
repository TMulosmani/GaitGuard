"""
report.py — Generate a plain-English PDF summary after each GaitGuard session.

The report embeds all three session plots and explains what each one means,
so teammates can understand a run without reading the source code.

Usage (called automatically by run_pipeline.py):
    from report import generate_report
    generate_report(results, twin, profile, session_dir, source, condition)
"""
from __future__ import annotations

import os
from datetime import datetime
from typing import List

import numpy as np

from core.types import DigitalTwin, GaitProfile, StrideResult


# ---------------------------------------------------------------------------
# Colour palette (RGB 0-1)
# ---------------------------------------------------------------------------
_GREEN  = (0.298, 0.686, 0.314)
_YELLOW = (1.000, 0.596, 0.000)
_RED    = (0.957, 0.263, 0.212)
_BLUE   = (0.086, 0.396, 0.753)
_DARK   = (0.15,  0.15,  0.15)
_MID    = (0.40,  0.40,  0.40)
_LIGHT  = (0.93,  0.93,  0.93)
_WHITE  = (1.0,   1.0,   1.0)


def generate_report(
    results: List[StrideResult],
    twin: DigitalTwin,
    profile: GaitProfile,
    session_dir: str,
    source: str = "synthetic",
    condition: str = "mixed",
) -> str:
    """
    Build session_report.pdf inside session_dir.
    Returns the absolute path to the created file.
    """
    from reportlab.lib.pagesizes import A4
    from reportlab.lib.units import cm
    from reportlab.lib import colors
    from reportlab.lib.styles import getSampleStyleSheet, ParagraphStyle
    from reportlab.lib.enums import TA_LEFT, TA_CENTER, TA_JUSTIFY
    from reportlab.platypus import (
        SimpleDocTemplate, Paragraph, Spacer, Table, TableStyle,
        Image, HRFlowable, PageBreak,
    )

    pdf_path = os.path.join(session_dir, "session_report.pdf")
    doc = SimpleDocTemplate(
        pdf_path,
        pagesize=A4,
        leftMargin=2.2 * cm,
        rightMargin=2.2 * cm,
        topMargin=2.0 * cm,
        bottomMargin=2.0 * cm,
        title="GaitGuard Session Report",
        author="GaitGuard",
    )

    W = A4[0] - 4.4 * cm   # usable width

    # ---- Styles -----------------------------------------------------------
    base = getSampleStyleSheet()

    def S(name, **kw):
        return ParagraphStyle(name, parent=base["Normal"], **kw)

    title_style   = S("T", fontSize=22, textColor=colors.HexColor("#1565c0"),
                       spaceAfter=4, leading=26, alignment=TA_LEFT,
                       fontName="Helvetica-Bold")
    sub_style     = S("Sub", fontSize=11, textColor=colors.HexColor("#455a64"),
                       spaceAfter=2, leading=14, alignment=TA_LEFT)
    h2_style      = S("H2", fontSize=13, textColor=colors.HexColor("#1565c0"),
                       spaceBefore=14, spaceAfter=4, leading=16,
                       fontName="Helvetica-Bold")
    h3_style      = S("H3", fontSize=11, textColor=colors.HexColor("#37474f"),
                       spaceBefore=8, spaceAfter=3, leading=14,
                       fontName="Helvetica-Bold")
    body_style    = S("B", fontSize=9.5, textColor=colors.HexColor("#263238"),
                       leading=14, spaceAfter=4, alignment=TA_JUSTIFY)
    caption_style = S("Cap", fontSize=8.5, textColor=colors.HexColor("#546e7a"),
                       leading=12, spaceAfter=2, alignment=TA_CENTER,
                       fontName="Helvetica-Oblique")
    bullet_style  = S("Bul", fontSize=9.5, textColor=colors.HexColor("#263238"),
                       leading=14, spaceAfter=2, leftIndent=12,
                       bulletIndent=0)

    def HR():
        return HRFlowable(width="100%", thickness=0.5,
                          color=colors.HexColor("#b0bec5"), spaceAfter=6)

    def bullet(text):
        return Paragraph(f"• {text}", bullet_style)

    # ---- Derived stats ----------------------------------------------------
    scores  = [r.gait_health_score for r in results]
    n       = len(results)
    mean_g  = float(np.mean(scores)) if n else 0.0
    min_g   = float(np.min(scores))  if n else 0.0
    max_g   = float(np.max(scores))  if n else 0.0
    green_c = sum(1 for s in scores if s >= 80)
    yellow_c= sum(1 for s in scores if 50 <= s < 80)
    red_c   = sum(1 for s in scores if s < 50)

    from collections import Counter
    haptic_counts = Counter(r.haptic.value for r in results)

    overall_label, overall_hex = (
        ("Good",    "#4caf50") if mean_g >= 80 else
        ("Fair",    "#ff9800") if mean_g >= 50 else
        ("Poor",    "#f44336")
    )

    session_ts = os.path.basename(session_dir)
    try:
        dt = datetime.strptime(session_ts, "%Y%m%d_%H%M%S")
        date_str = dt.strftime("%B %d, %Y  %H:%M")
    except ValueError:
        date_str = session_ts

    source_label = {
        "synthetic": f"Synthetic ({condition})",
        "compwalk":  f"COMPWALK-ACL ({condition})",
    }.get(source, source)

    # ======================================================================
    # STORY
    # ======================================================================
    story = []

    # ------------------------------------------------------------------
    # PAGE 1 — Cover / Session Summary
    # ------------------------------------------------------------------
    story.append(Paragraph("GaitGuard", title_style))
    story.append(Paragraph("Session Report", sub_style))
    story.append(HR())
    story.append(Spacer(1, 0.2 * cm))

    # Metadata row
    meta_data = [
        ["Date", date_str],
        ["Data source", source_label],
        ["Strides monitored", str(n)],
        ["Overall rating", overall_label],
    ]
    meta_table = Table(meta_data, colWidths=[4 * cm, W - 4 * cm])
    meta_table.setStyle(TableStyle([
        ("FONTNAME",    (0, 0), (0, -1), "Helvetica-Bold"),
        ("FONTSIZE",    (0, 0), (-1, -1), 9.5),
        ("TEXTCOLOR",   (0, 0), (0, -1), colors.HexColor("#455a64")),
        ("TEXTCOLOR",   (1, 0), (1, -1), colors.HexColor("#263238")),
        ("ROWBACKGROUNDS", (0, 0), (-1, -1),
         [colors.HexColor("#f5f5f5"), colors.white]),
        ("BOTTOMPADDING", (0, 0), (-1, -1), 5),
        ("TOPPADDING",    (0, 0), (-1, -1), 5),
        ("LEFTPADDING",   (0, 0), (-1, -1), 8),
        ("TEXTCOLOR",   (1, 3), (1, 3), colors.HexColor(overall_hex)),
        ("FONTNAME",    (1, 3), (1, 3), "Helvetica-Bold"),
    ]))
    story.append(meta_table)
    story.append(Spacer(1, 0.5 * cm))

    # Scores summary table
    story.append(Paragraph("Gait Health Scores", h2_style))
    score_data = [
        ["Metric", "Value"],
        ["Mean GHS",    f"{mean_g:.1f}"],
        ["Best stride", f"{max_g:.1f}"],
        ["Worst stride",f"{min_g:.1f}"],
        ["Good strides (≥80)",   f"{green_c}  ({100*green_c/n:.0f}%)" if n else "—"],
        ["Fair strides (50–79)", f"{yellow_c} ({100*yellow_c/n:.0f}%)" if n else "—"],
        ["Poor strides (<50)",   f"{red_c}  ({100*red_c/n:.0f}%)" if n else "—"],
    ]
    col_w = [W * 0.6, W * 0.4]
    score_table = Table(score_data, colWidths=col_w)
    score_table.setStyle(TableStyle([
        ("BACKGROUND",   (0, 0), (-1, 0), colors.HexColor("#1565c0")),
        ("TEXTCOLOR",    (0, 0), (-1, 0), colors.white),
        ("FONTNAME",     (0, 0), (-1, 0), "Helvetica-Bold"),
        ("FONTSIZE",     (0, 0), (-1, -1), 9.5),
        ("ROWBACKGROUNDS", (0, 1), (-1, -1),
         [colors.HexColor("#f5f5f5"), colors.white]),
        ("BOTTOMPADDING", (0, 0), (-1, -1), 5),
        ("TOPPADDING",    (0, 0), (-1, -1), 5),
        ("LEFTPADDING",   (0, 0), (-1, -1), 8),
        ("TEXTCOLOR",    (1, 4), (1, 4), colors.HexColor("#4caf50")),
        ("TEXTCOLOR",    (1, 5), (1, 5), colors.HexColor("#ff9800")),
        ("TEXTCOLOR",    (1, 6), (1, 6), colors.HexColor("#f44336")),
        ("FONTNAME",     (1, 4), (1, 6), "Helvetica-Bold"),
    ]))
    story.append(score_table)
    story.append(Spacer(1, 0.4 * cm))

    # Haptic summary
    story.append(Paragraph("Haptic Feedback Triggered", h2_style))
    haptic_rows = [["Pattern", "Count", "What it means"]]
    haptic_info = {
        "two_short":   "Insufficient knee extension at heel strike",
        "one_long":    "Reduced foot clearance during swing phase",
        "three_short": "General high deviation from healthy twin",
        "none":        "Gait within acceptable range (no alert)",
    }
    for key, label in haptic_info.items():
        c = haptic_counts.get(key, 0)
        haptic_rows.append([key.replace("_", " ").title(), str(c), label])

    haptic_table = Table(haptic_rows, colWidths=[W*0.22, W*0.1, W*0.68])
    haptic_table.setStyle(TableStyle([
        ("BACKGROUND",   (0, 0), (-1, 0), colors.HexColor("#37474f")),
        ("TEXTCOLOR",    (0, 0), (-1, 0), colors.white),
        ("FONTNAME",     (0, 0), (-1, 0), "Helvetica-Bold"),
        ("FONTSIZE",     (0, 0), (-1, -1), 9),
        ("ROWBACKGROUNDS", (0, 1), (-1, -1),
         [colors.HexColor("#f5f5f5"), colors.white]),
        ("BOTTOMPADDING", (0, 0), (-1, -1), 5),
        ("TOPPADDING",    (0, 0), (-1, -1), 5),
        ("LEFTPADDING",   (0, 0), (-1, -1), 8),
    ]))
    story.append(haptic_table)

    story.append(PageBreak())

    # ------------------------------------------------------------------
    # PAGE 2 — How GaitGuard Works
    # ------------------------------------------------------------------
    story.append(Paragraph("How GaitGuard Works", h2_style))
    story.append(HR())
    story.append(Paragraph(
        "GaitGuard processes motion sensor data through four sequential phases "
        "to produce a personalised real-time assessment of gait quality. "
        "Each phase builds on the previous one.",
        body_style,
    ))
    story.append(Spacer(1, 0.3 * cm))

    phases = [
        ("Phase 0 — Calibration (2 seconds)",
         "The patient stands still while three IMU sensors on the thigh, shin, and foot "
         "record baseline angles. This removes sensor mounting offset so all subsequent "
         "angles are measured relative to the patient's own neutral standing posture. "
         "No walking data is used here."),
        ("Phase 1 — Stride Segmentation (≥20 strides)",
         "The patient walks normally. The system detects each heel-strike using three "
         "simultaneous conditions: the foot gyroscope drops below 15°/s, the foot "
         "accelerometer reads close to 1g (flat on the ground), and the knee is near "
         "its calibrated zero. Each detected stride is filtered and time-normalised "
         "to 100 equal timepoints. After 20 valid strides are collected, a personal "
         "gait profile is built — mean waveform, variability, and a 30-point anchor "
         "segment representing the patient's characteristic stance phase (first 30% "
         "of the gait cycle)."),
        ("Phase 2 — Digital Twin Generation",
         "The 30-point anchor from Phase 1 is passed to a two-layer LSTM neural network "
         "trained on healthy gait data. The model predicts what the remaining 70 points "
         "of the gait cycle should look like for a healthy walker with similar stance "
         "characteristics. This prediction is the patient's personalised "
         "Healthy Digital Twin — a reference that accounts for their own body mechanics "
         "rather than a generic population average."),
        ("Phase 3 — Real-Time Monitoring",
         "Every new stride is scored against the Digital Twin. The absolute difference "
         "between observed and twin waveforms is computed for the knee (60% weight) "
         "and ankle (40% weight), then normalised by the patient's own stride-to-stride "
         "variability from Phase 1. The resulting Gait Health Score (0–100) reflects "
         "how closely the current stride matches the twin. If deviation is large, "
         "a haptic vibration pattern is triggered on the wearable device to cue "
         "the patient in real time."),
    ]
    for title_txt, body_txt in phases:
        story.append(Paragraph(title_txt, h3_style))
        story.append(Paragraph(body_txt, body_style))

    story.append(Spacer(1, 0.4 * cm))
    story.append(Paragraph("Gait Health Score Colour Scale", h3_style))

    ghs_legend = [
        ["Score range", "Colour", "Interpretation"],
        ["80 – 100",    "Green",  "Gait closely matches the healthy twin. No correction needed."],
        ["50 – 79",     "Yellow", "Moderate deviation. Monitor; consider feedback."],
        ["0 – 49",      "Red",    "Significant deviation. Haptic alert triggered."],
    ]
    ghs_legend_table = Table(ghs_legend, colWidths=[W*0.2, W*0.15, W*0.65])
    ghs_legend_table.setStyle(TableStyle([
        ("BACKGROUND",   (0, 0), (-1, 0), colors.HexColor("#37474f")),
        ("TEXTCOLOR",    (0, 0), (-1, 0), colors.white),
        ("FONTNAME",     (0, 0), (-1, 0), "Helvetica-Bold"),
        ("FONTSIZE",     (0, 0), (-1, -1), 9),
        ("ROWBACKGROUNDS", (0, 1), (-1, -1),
         [colors.HexColor("#f5f5f5"), colors.white]),
        ("BOTTOMPADDING", (0, 0), (-1, -1), 5),
        ("TOPPADDING",    (0, 0), (-1, -1), 5),
        ("LEFTPADDING",   (0, 0), (-1, -1), 8),
        ("TEXTCOLOR",    (1, 1), (1, 1), colors.HexColor("#4caf50")),
        ("TEXTCOLOR",    (1, 2), (1, 2), colors.HexColor("#ff9800")),
        ("TEXTCOLOR",    (1, 3), (1, 3), colors.HexColor("#f44336")),
        ("FONTNAME",     (1, 1), (1, 3), "Helvetica-Bold"),
    ]))
    story.append(ghs_legend_table)

    story.append(PageBreak())

    # ------------------------------------------------------------------
    # PAGE 3 — Overlay Chart
    # ------------------------------------------------------------------
    overlay_path = os.path.join(session_dir, "overlay.png")
    if os.path.exists(overlay_path):
        story.append(Paragraph("Chart 1 — Observed vs. Healthy Digital Twin", h2_style))
        story.append(HR())
        story.append(Image(overlay_path, width=W, height=W * 0.58))
        story.append(Spacer(1, 0.15 * cm))
        story.append(Paragraph("Figure 1: Knee (top) and ankle (bottom) joint angles across the gait cycle.", caption_style))
        story.append(Spacer(1, 0.3 * cm))

        story.append(Paragraph("How to read this chart", h3_style))
        items = [
            "<b>X-axis (0–100%)</b> is one complete gait cycle, from one heel-strike to the next. "
            "0% = heel strike, ~60% = toe-off, 100% = next heel strike.",
            "<b>Solid blue / green line</b> is the Healthy Digital Twin — what the joint angle "
            "should look like for a healthy walker with this patient's stance phase.",
            "<b>Dashed pink line</b> is the patient's own mean waveform collected during Phase 1 calibration walks.",
            "<b>Pink shaded band</b> is ±1 standard deviation of the patient's strides — their natural variability.",
            "<b>Thin coloured lines</b> are the last 10 individual monitored strides overlaid, showing consistency.",
            "<b>Dotted vertical line at 30%</b> marks the anchor boundary — the LSTM uses everything to the left "
            "to predict everything to the right.",
        ]
        for item in items:
            story.append(bullet(item))
            story.append(Spacer(1, 0.1 * cm))

        story.append(Spacer(1, 0.3 * cm))
        story.append(Paragraph("What to look for", h3_style))
        story.append(Paragraph(
            "A healthy session shows the observed strides tracking close to the twin line with "
            "the patient mean overlapping it. "
            "In this session the patient mean for knee flexion peaked at "
            f"~{profile.mean_knee.max():.0f}° versus the twin peak of "
            f"~{twin.twin_knee.max():.0f}°. "
            "A large gap between the dashed line and the solid line — especially in the swing "
            "phase (40–80%) for the knee, or push-off (55–70%) for the ankle — indicates the "
            "deviation that drives a low Gait Health Score.",
            body_style,
        ))

    story.append(PageBreak())

    # ------------------------------------------------------------------
    # PAGE 4 — GHS Trend
    # ------------------------------------------------------------------
    ghs_path = os.path.join(session_dir, "ghs_trend.png")
    if os.path.exists(ghs_path):
        story.append(Paragraph("Chart 2 — Gait Health Score Per Stride", h2_style))
        story.append(HR())
        story.append(Image(ghs_path, width=W, height=W * 0.35))
        story.append(Spacer(1, 0.15 * cm))
        story.append(Paragraph("Figure 2: GHS for every monitored stride. Green ≥ 80, yellow 50–79, red < 50.", caption_style))
        story.append(Spacer(1, 0.3 * cm))

        story.append(Paragraph("How to read this chart", h3_style))
        items = [
            "<b>Each bar</b> is one stride. Height is the Gait Health Score (0 = worst, 100 = best).",
            "<b>Green dashed line at 80</b> — above this the stride is considered healthy.",
            "<b>Yellow dashed line at 50</b> — below this a haptic alert may fire.",
            "<b>Bar colour</b> reflects the same thresholds: green / yellow / red.",
            "<b>Trend over time</b> — a patient improving during a session will show bars rising "
            "from red/yellow toward green as they receive real-time haptic feedback.",
        ]
        for item in items:
            story.append(bullet(item))
            story.append(Spacer(1, 0.1 * cm))

        story.append(Spacer(1, 0.3 * cm))
        story.append(Paragraph("This session", h3_style))
        trend_note = (
            f"Mean GHS was <b>{mean_g:.1f}</b> ({overall_label}). "
            f"{green_c} strides were green, {yellow_c} yellow, {red_c} red "
            f"out of {n} total monitored strides. "
        )
        if red_c > n * 0.5:
            trend_note += (
                "The majority of strides scored in the red zone, indicating consistent "
                "deviation from the healthy twin. This is expected for pathological gait data "
                "and confirms the system is detecting the abnormality."
            )
        elif green_c > n * 0.7:
            trend_note += (
                "Most strides were in the green zone, indicating gait closely matched "
                "the healthy digital twin throughout the session."
            )
        else:
            trend_note += (
                "Mixed scores suggest intermittent deviation — the patient may be "
                "self-correcting in response to haptic feedback or showing fatigue."
            )
        story.append(Paragraph(trend_note, body_style))

    story.append(PageBreak())

    # ------------------------------------------------------------------
    # PAGE 5 — Deviation Heatmap
    # ------------------------------------------------------------------
    heatmap_path = os.path.join(session_dir, "deviation_heatmap.png")
    if os.path.exists(heatmap_path):
        story.append(Paragraph("Chart 3 — Deviation Heatmap", h2_style))
        story.append(HR())
        story.append(Image(heatmap_path, width=W, height=W * 0.50))
        story.append(Spacer(1, 0.15 * cm))
        story.append(Paragraph(
            "Figure 3: Absolute deviation (°) from the Digital Twin per timepoint per stride. "
            "Top = knee, bottom = ankle. Darker red = larger deviation.",
            caption_style,
        ))
        story.append(Spacer(1, 0.3 * cm))

        story.append(Paragraph("How to read this chart", h3_style))
        items = [
            "<b>X-axis (31–100%)</b> covers the post-anchor portion of the gait cycle — the region the LSTM predicted.",
            "<b>Y-axis</b> is each stride number in chronological order (stride 1 at the top).",
            "<b>Cell colour</b> shows how many degrees the observed angle deviated from the twin at that exact timepoint. "
            "White / pale yellow = small error, orange = moderate, dark red = large error.",
            "<b>Vertical bands of red</b> pinpoint specific phases of the cycle where the patient consistently struggles — "
            "e.g. a red column around 60–80% on the knee heatmap means reduced peak swing flexion every stride.",
            "<b>Horizontal banding</b> (some strides uniformly darker) indicates inconsistent strides, "
            "possibly due to stumbling, distraction, or fatigue.",
        ]
        for item in items:
            story.append(bullet(item))
            story.append(Spacer(1, 0.1 * cm))

        story.append(Spacer(1, 0.3 * cm))
        story.append(Paragraph("What the heatmap tells clinicians", h3_style))

        # Find worst knee and ankle zones
        if results:
            knee_mat  = np.stack([r.knee_dev  for r in results])   # (S, 80)
            ankle_mat = np.stack([r.ankle_dev for r in results])   # (S, 80)
            knee_mean_t  = knee_mat.mean(axis=0)
            ankle_mean_t = ankle_mat.mean(axis=0)
            worst_knee_tp  = int(knee_mean_t.argmax())  + 21
            worst_ankle_tp = int(ankle_mean_t.argmax()) + 21

            story.append(Paragraph(
                f"In this session the largest average knee deviation occurred at gait-cycle point "
                f"<b>{worst_knee_tp}%</b> "
                f"({_tp_label(worst_knee_tp)}) "
                f"and the largest ankle deviation at <b>{worst_ankle_tp}%</b> "
                f"({_tp_label(worst_ankle_tp)}). "
                "These hotspots correspond directly to the haptic patterns triggered: "
                "deviations in 30–45% fire the knee-extension cue (two short pulses), "
                "deviations in 60–85% fire the foot-clearance cue (one long pulse).",
                body_style,
            ))

    # ------------------------------------------------------------------
    # Build
    # ------------------------------------------------------------------
    doc.build(story)
    print(f"[Report] PDF saved → {pdf_path}")
    return pdf_path


# ---------------------------------------------------------------------------
# Helper
# ---------------------------------------------------------------------------

def _tp_label(tp: int) -> str:
    """Return a plain-English gait-cycle phase label for a timepoint 0-100."""
    if tp < 12:
        return "initial contact / loading response"
    if tp < 30:
        return "mid-stance"
    if tp < 50:
        return "terminal stance"
    if tp < 62:
        return "pre-swing / push-off"
    if tp < 75:
        return "initial swing"
    if tp < 87:
        return "mid-swing"
    return "terminal swing"

"""
Pinewood Preparatory School - Report Card Generator
Supports 3 report types:
  1. Beginners/Middle Class  - skills checklist (Not Yet / Beginning / Satisfactory / Good)
  2. Grade 1 & 2             - subject test scores with classwork grade
  3. Grade 7                 - subject marks, grades, attainment & effort
"""

import os
from reportlab.lib.pagesizes import A4
from reportlab.lib import colors
from reportlab.lib.units import mm
from reportlab.lib.styles import getSampleStyleSheet, ParagraphStyle
from reportlab.platypus import (
    SimpleDocTemplate, Paragraph, Spacer, Table, TableStyle,
    HRFlowable, KeepTogether
)
from reportlab.lib.enums import TA_CENTER, TA_LEFT, TA_RIGHT

# ── Page geometry ──────────────────────────────────────────────────────────────
PAGE_W, PAGE_H = A4
MARGIN      = 15 * mm          # left = right = top = bottom
CONTENT_W   = PAGE_W - 2 * MARGIN   # 180 mm  — every table must fill exactly this
HALF_W      = CONTENT_W / 2         # 90 mm   — left col of any 2-col wrapper
# Inner table widths when sitting inside a wrapper cell (leaves 2mm gap on each side)
INNER_LABEL = 55 * mm          # label/name column of side-by-side mini-tables
INNER_VALUE = HALF_W - INNER_LABEL - 4 * mm  # 31 mm  — value column
INNER_TABLE_W = HALF_W - 4 * mm  # 86 mm — total width of tables inside wrapper

# ── Brand colours ──────────────────────────────────────────────────────────────
GREEN       = colors.HexColor("#6aab2e")
LIGHT_GREEN = colors.HexColor("#d6efc1")
DARK_GREEN  = colors.HexColor("#4a7c1f")
ROW_ALT     = colors.HexColor("#f5f5f5")

# ── Styles ─────────────────────────────────────────────────────────────────────
def make_styles():
    return {
        "school":   ParagraphStyle("school",   fontSize=20,  fontName="Helvetica-Bold",
                                   textColor=DARK_GREEN, alignment=TA_CENTER, spaceAfter=2),
        "address":  ParagraphStyle("address",  fontSize=7.5, fontName="Helvetica",
                                   textColor=colors.grey, alignment=TA_CENTER, spaceAfter=6),
        "banner":   ParagraphStyle("banner",   fontSize=10,  fontName="Helvetica-Bold",
                                   textColor=colors.white, alignment=TA_CENTER),
        "label":    ParagraphStyle("label",    fontSize=8,   fontName="Helvetica",
                                   textColor=colors.grey),
        "value":    ParagraphStyle("value",    fontSize=9,   fontName="Helvetica-Bold",
                                   textColor=colors.black),
        "section":  ParagraphStyle("section",  fontSize=9,   fontName="Helvetica-Bold",
                                   textColor=colors.white, alignment=TA_LEFT),
        "cell":     ParagraphStyle("cell",     fontSize=8.5, fontName="Helvetica", leading=12),
        "footer":   ParagraphStyle("footer",   fontSize=7.5, fontName="Helvetica-Oblique",
                                   textColor=DARK_GREEN, alignment=TA_CENTER),
    }

S = make_styles()

# ── Wrapper table style (adds 2mm horizontal padding to create a gap between columns) ─
WRAPPER_STYLE = TableStyle([
    ("VALIGN",        (0, 0), (-1, -1), "TOP"),
    ("LEFTPADDING",   (0, 0), (0, -1), 2 * mm),
    ("RIGHTPADDING",  (0, 0), (0, -1), 2 * mm),
    ("LEFTPADDING",   (1, 0), (1, -1), 2 * mm),
    ("RIGHTPADDING",  (1, 0), (1, -1), 2 * mm),
    ("TOPPADDING",    (0, 0), (-1, -1), 0),
    ("BOTTOMPADDING", (0, 0), (-1, -1), 0),
])

def _wrapper(left, right):
    """Place two flowables side-by-side, each exactly HALF_W wide."""
    t = Table([[left, right]], colWidths=[HALF_W, HALF_W])
    t.setStyle(WRAPPER_STYLE)
    return t

# ── Shared helpers ─────────────────────────────────────────────────────────────
def _header_block(meta: dict, school=None) -> list:
    """School heading + address + ASSESSMENT REPORT banner + pupil info table."""
    elems = []

    school_name = school.name if school else "School Name"
    elems.append(Paragraph(school_name, S["school"]))

    if school:
        addr_parts = []
        if school.address_line1:
            addr_parts.append(school.address_line1)
        if school.address_line2:
            addr_parts.append(school.address_line2)
        if school.city:
            addr_parts.append(school.city)
        address_str = ", ".join(addr_parts) if addr_parts else ""
        contact_parts = []
        if school.phone:
            contact_parts.append(school.phone)
        if school.email:
            contact_parts.append(school.email)
        if school.website:
            contact_parts.append(school.website)
        contact_str = " | ".join(contact_parts) if contact_parts else ""
        address_html = (address_str + "<br/>" + contact_str) if address_str or contact_str else ""
    else:
        address_html = ""

    elems.append(Paragraph(address_html, S["address"]))

    # Green banner — exactly CONTENT_W wide
    banner_tbl = Table([[Paragraph("ASSESSMENT REPORT", S["banner"])]],
                       colWidths=[CONTENT_W])
    banner_tbl.setStyle(TableStyle([
        ("BACKGROUND",    (0, 0), (-1, -1), GREEN),
        ("TOPPADDING",    (0, 0), (-1, -1), 5),
        ("BOTTOMPADDING", (0, 0), (-1, -1), 5),
        ("LEFTPADDING",   (0, 0), (-1, -1), 4),
        ("RIGHTPADDING",  (0, 0), (-1, -1), 4),
    ]))
    elems.append(banner_tbl)
    elems.append(Spacer(1, 4 * mm))

    # Pupil meta — columns sum to CONTENT_W
    # 28+22+18+16+26+40+30 = 180 mm (Term column widened from 8mm to 30mm)
    col_w = [28*mm, 22*mm, 18*mm, 16*mm, 26*mm, 40*mm, 30*mm]
    keys   = ["Name of pupil", "Class", "Admn No.", "Age",
              "Average age of grade", "Class teacher(s)", "Term"]
    values = [meta.get("name",""), meta.get("class",""), meta.get("admn",""),
              meta.get("age",""),  meta.get("avg_age",""),
              meta.get("teachers",""), meta.get("term","")]

    info_tbl = Table(
        [[Paragraph(k, S["label"]) for k in keys],
         [Paragraph(v, S["value"]) for v in values]],
        colWidths=col_w
    )
    info_tbl.setStyle(TableStyle([
        ("TOPPADDING",    (0, 0), (-1, -1), 1),
        ("BOTTOMPADDING", (0, 0), (-1, -1), 1),
        ("LEFTPADDING",   (0, 0), (-1, -1), 2),
        ("RIGHTPADDING",  (0, 0), (-1, -1), 2),
        ("VALIGN",        (0, 0), (-1, -1), "TOP"),
        ("GRID",          (0, 0), (-1, -1), 0.4, colors.HexColor("#cccccc")),
    ]))
    elems.append(info_tbl)
    elems.append(Spacer(1, 2 * mm))
    
    # Next term commences — placed in a bordered table to align with the columns above
    next_term_tbl = Table([
        [Paragraph("Next term commences", S["label"]), 
         Paragraph(meta.get("next_term", ""), S["value"])]
    ], colWidths=[40*mm, CONTENT_W - 40*mm])
    next_term_tbl.setStyle(TableStyle([
        ("TOPPADDING",    (0, 0), (-1, -1), 1),
        ("BOTTOMPADDING", (0, 0), (-1, -1), 1),
        ("LEFTPADDING",   (0, 0), (-1, -1), 2),
        ("RIGHTPADDING",  (0, 0), (-1, -1), 2),
        ("VALIGN",        (0, 0), (-1, -1), "TOP"),
        ("GRID",          (0, 0), (-1, -1), 0.4, colors.HexColor("#cccccc")),
    ]))
    elems.append(next_term_tbl)
    elems.append(Spacer(1, 4 * mm))
    return elems


def _footer() -> list:
    return [
        Spacer(1, 6 * mm),
        HRFlowable(width="100%", thickness=0.5, color=GREEN),
        Paragraph(
            "Pro 22:6 KJV  Train up a child in the way he should go: "
            "and when he is old, he will not depart from it.",
            S["footer"]),
    ]


def _base_table_style(font_size=8.5, header_rows=1):
    """Standard table style shared across all templates."""
    return TableStyle([
        ("BACKGROUND",    (0, 0),          (-1, header_rows - 1), GREEN),
        ("TEXTCOLOR",     (0, 0),          (-1, header_rows - 1), colors.white),
        ("FONTNAME",      (0, 0),          (-1, header_rows - 1), "Helvetica-Bold"),
        ("FONTSIZE",      (0, 0),          (-1, -1),              font_size),
        ("ROWBACKGROUNDS",(0, header_rows),(-1, -1),              [colors.white, ROW_ALT]),
        ("GRID",          (0, 0),          (-1, -1),              0.4, colors.HexColor("#cccccc")),
        ("TOPPADDING",    (0, 0),          (-1, -1),              3),
        ("BOTTOMPADDING", (0, 0),          (-1, -1),              3),
        ("LEFTPADDING",   (0, 0),          (-1, -1),              4),
        ("RIGHTPADDING",  (0, 0),          (-1, -1),              4),
        ("ALIGN",         (1, 0),          (-1, -1),              "CENTER"),
        ("VALIGN",        (0, 0),          (-1, -1),              "MIDDLE"),
    ])


def _mini_table(rows: list, col_widths: list) -> Table:
    """Two-column key/value table with green header row, fits inside HALF_W."""
    tbl = Table(rows, colWidths=col_widths)
    tbl.setStyle(_base_table_style(font_size=8))
    # Override: left-align first column values
    tbl.setStyle(TableStyle([
        ("ALIGN", (0, 1), (0, -1), "LEFT"),
    ]))
    return tbl


def _list_table(title: str, items: list, width: float = INNER_TABLE_W) -> Table:
    """Single-column list table with a green header, width defaults to INNER_TABLE_W."""
    rows = [[title]] + [[it] for it in (items or ["-"])]
    tbl = Table(rows, colWidths=[width])
    tbl.setStyle(_base_table_style(font_size=8))
    tbl.setStyle(TableStyle([("ALIGN", (0, 1), (-1, -1), "LEFT")]))
    return tbl


def _grade_scale_table(gs: dict, available_width: float) -> Table:
    """Renders the grade-scale box to fit exactly within available_width."""
    grade_keys = list(gs.keys())
    label_col  = 32 * mm
    grade_col  = (available_width - label_col) / len(grade_keys)

    header = ["Grade"]        + grade_keys
    mins   = ["Minimum score"]+ [str(gs[k]["min"])  for k in grade_keys]
    descs  = ["Description"]  + [gs[k]["desc"]      for k in grade_keys]

    inner = Table([header, mins, descs],
                  colWidths=[label_col] + [grade_col] * len(grade_keys))
    inner.setStyle(TableStyle([
        ("BACKGROUND",    (0, 0), (-1, 0),  GREEN),
        ("TEXTCOLOR",     (0, 0), (-1, 0),  colors.white),
        ("FONTNAME",      (0, 0), (-1, -1), "Helvetica-Bold"),
        ("FONTSIZE",      (0, 0), (-1, -1), 7.5),
        ("ROWBACKGROUNDS",(0, 1), (-1, -1), [LIGHT_GREEN, colors.white]),
        ("GRID",          (0, 0), (-1, -1), 0.4, colors.HexColor("#cccccc")),
        ("TOPPADDING",    (0, 0), (-1, -1), 3),
        ("BOTTOMPADDING", (0, 0), (-1, -1), 3),
        ("LEFTPADDING",   (0, 0), (-1, -1), 4),
        ("RIGHTPADDING",  (0, 0), (-1, -1), 4),
        # Apply alignments separately to avoid override issues
        ("ALIGN",         (0, 0), (0,  -1), "LEFT"),
        ("ALIGN",         (1, 0), (-1, -1), "CENTER"),
        ("VALIGN",        (0, 0), (-1, -1), "MIDDLE"),
    ]))

    # Removed backColor from ParagraphStyle to allow table cell background to show
    title_p = Paragraph(
        f"Scholastic Grade Scale: Grades are awarded on a "
        f"{len(gs)} point grading scale as follows",
        ParagraphStyle("gs_title", fontSize=7.5, fontName="Helvetica-Bold",
                       alignment=TA_CENTER,
                       spaceAfter=0, spaceBefore=0))

    outer = Table([[title_p], [inner]], colWidths=[available_width])
    outer.setStyle(TableStyle([
        ("BACKGROUND",    (0, 0), (0, 0), LIGHT_GREEN),
        # Removed top/bottom padding to eliminate gap between title and inner grid
        ("TOPPADDING",    (0, 0), (-1, -1), 0),
        ("BOTTOMPADDING", (0, 0), (-1, -1), 0),
        ("LEFTPADDING",   (0, 0), (-1, -1), 0),
        ("RIGHTPADDING",  (0, 0), (-1, -1), 0),
    ]))
    return outer


# ══════════════════════════════════════════════════════════════════════════════
# TEMPLATE 1 – Beginners / Middle Class  (skills checklist)
# ══════════════════════════════════════════════════════════════════════════════
SKILL_SECTIONS = {
    "MOTOR SKILLS": [
        "Walks, runs and jumps easily.",
        "Can throw a ball to a partner.",
        "Can catch a ball.",
        "Can climb stairs without hands.",
        "Holds pencil, crayon etc. correctly.",
        "Can cut with scissors.",
        "Can manipulate small objects.",
        "Can pour water without spilling.",
    ],
    "CONCEPTUAL SKILLS": [
        "Can complete a simple inset puzzle.",
        "Does simple interlocking jigsaw.",
        "Can recognise and match colours.",
        "Recognises main shapes.",
        "Can sort objects into groups on basis of common feature e.g. colour.",
        "Can match on one-to-one basis e.g. a cup to each saucer.",
        "Counts objects up to ten.",
        "Counts objects up to twenty.",
        "Can write numbers up to 10.",
        "Can recognise letters A – Z.",
        "Can write letters A – Z.",
        "Can recognise own name.",
        "Knows different lengths of time.",
        "Knows about more or less in volume, weight and quantity.",
        "Understands conservation of volume.",
        "Can recognise a familiar melody.",
    ],
    "COMMUNICATION SKILLS": [
        "Speaks clearly – can be understood.",
        "Uses sentence of 5 words +.",
        "Asks questions demanding explanations.",
        "Can answer questions correctly.",
        "Can express ideas clearly.",
        "Can write own name.",
        "Can carry a message correctly.",
        "Shows interest in stories.",
        "Shows interest in books.",
        "Participates in dramatic activities.",
        "Can recite 12 or more nursery rhymes or songs.",
    ],
    "CREATIVE SKILLS": [
        "Makes representational drawings.",
        "Paints scenes and can talk about them.",
        "Uses clay to make recognisable objects.",
        "Uses material in individual ways.",
        "Plays imaginatively e.g. with blocks.",
        "Appreciates others' creative work.",
    ],
    "SOCIAL SKILLS": [
        "Likes to be independent.",
        "Plays alongside other children.",
        "Plays with other children.",
        "Joins in group activities.",
        "Shares with other children.",
        "Co-operates with adults.",
        "Knows how to greet strangers.",
        "Willing to help with jobs e.g. tidying up.",
    ],
    "CONCENTRATION SKILLS": [
        "Can concentrate on a chosen activity for 5 minutes.",
        "Can concentrate on a chosen activity for 10 minutes.",
        "Can concentrate on a chosen activity for 15 minutes.",
        "Usually completes activities.",
        "Will persist with things found difficult.",
        "Able to listen to short passages of music.",
    ],
}

RATING_COLS = ["NOT YET", "BEGINNING", "SATISFACTORY", "GOOD"]


def _skills_table(skills_data: dict) -> list:
    """
    Builds the full skills checklist table filling exactly CONTENT_W.
    Column widths: skill label = CONTENT_W - 4 equal tick columns.
    """
    N_TICK    = len(RATING_COLS)          # 4
    TICK_W    = 22 * mm                   # each tick column
    SKILL_W   = CONTENT_W - N_TICK * TICK_W   # 180 - 88 = 92 mm
    col_w     = [SKILL_W] + [TICK_W] * N_TICK

    rows = [["SKILLS"] + RATING_COLS]

    for section, items in SKILL_SECTIONS.items():
        rows.append([Paragraph(section, S["section"])] + [""] * N_TICK)
        for item in items:
            rating = skills_data.get(item, "")
            ticks  = ["✔" if rating == col else "" for col in RATING_COLS]
            rows.append([Paragraph(item, S["cell"])] + ticks)

    tbl = Table(rows, colWidths=col_w, repeatRows=1)

    cmds = [
        ("BACKGROUND",    (0, 0), (-1, 0),  GREEN),
        ("TEXTCOLOR",     (0, 0), (-1, 0),  colors.white),
        ("FONTNAME",      (0, 0), (-1, 0),  "Helvetica-Bold"),
        ("FONTSIZE",      (0, 0), (-1, -1), 8),
        ("GRID",          (0, 0), (-1, -1), 0.4, colors.HexColor("#cccccc")),
        ("TOPPADDING",    (0, 0), (-1, -1), 3),
        ("BOTTOMPADDING", (0, 0), (-1, -1), 3),
        ("LEFTPADDING",   (0, 0), (-1, -1), 4),
        ("RIGHTPADDING",  (0, 0), (-1, -1), 4),
        ("ALIGN",         (1, 0), (-1, -1), "CENTER"),
        ("VALIGN",        (0, 0), (-1, -1), "MIDDLE"),
        ("FONTNAME",      (1, 1), (-1, -1), "Helvetica-Bold"),
        ("TEXTCOLOR",     (1, 1), (-1, -1), DARK_GREEN),
    ]

    r = 1
    for section, items in SKILL_SECTIONS.items():
        cmds += [
            ("BACKGROUND", (0, r), (-1, r), DARK_GREEN),
            ("TEXTCOLOR",  (0, r), (-1, r), colors.white),
            ("SPAN",       (0, r), (-1, r)),
            ("FONTNAME",   (0, r), (-1, r), "Helvetica-Bold"),
        ]
        r += 1
        for i in range(len(items)):
            bg = colors.white if i % 2 == 0 else ROW_ALT
            cmds.append(("BACKGROUND", (0, r + i), (-1, r + i), bg))
        r += len(items)

    tbl.setStyle(TableStyle(cmds))
    return [tbl]


def generate_beginners_report(meta: dict, skills_data: dict,
                               project_work: dict, attendance: dict,
                               output_path: str, school=None):
    """
    meta         – {name, class, admn, age, avg_age, teachers, term, next_term}
    skills_data  – {skill_text: "NOT YET"|"BEGINNING"|"SATISFACTORY"|"GOOD"}
    project_work – {Submission, Presentation, Effort}
    attendance   – {present, absent}
    school       – School model instance with branding data
    """
    doc = SimpleDocTemplate(output_path, pagesize=A4,
                            leftMargin=MARGIN, rightMargin=MARGIN,
                            topMargin=MARGIN, bottomMargin=MARGIN)
    story = _header_block(meta, school=school) + _skills_table(skills_data)
    story.append(Spacer(1, 4 * mm))

    pw_rows  = [["PROJECT WORK",    meta.get("term", "")],
                ["Submission",      project_work.get("Submission", "")],
                ["Presentation",    project_work.get("Presentation", "")],
                ["Effort",          project_work.get("Effort", "")]]
    att_rows = [["Attendance",         meta.get("term", "")],
                ["No. of days present", str(attendance.get("present", ""))],
                ["No. of days absent",  str(attendance.get("absent", ""))]]

    pw_tbl  = _mini_table(pw_rows,  [INNER_LABEL, INNER_VALUE])
    att_tbl = _mini_table(att_rows, [INNER_LABEL, INNER_VALUE])

    story.append(_wrapper(pw_tbl, att_tbl))
    story += _footer()
    doc.build(story)
    print(f"✔  Beginners report saved → {output_path}")


# ══════════════════════════════════════════════════════════════════════════════
# TEMPLATE 2 – Grade 1 & 2  (subject scores)
# ══════════════════════════════════════════════════════════════════════════════
def generate_grade12_report(meta: dict, subjects: list,
                             homework: dict, project_work: dict,
                             clubs: list, sports: list, other: list,
                             attendance: dict, grade_scale: dict,
                             output_path: str, school=None):
    """
    subjects   – [{name, classwork, test_pct, class_avg_pct}, …]
    homework / project_work – {Submission, Presentation, Effort}
    clubs / sports / other  – [str, …]
    attendance – {present, absent}
    grade_scale – {A: {min, desc}, …}  (None → 4-point default)
    school     – School model instance with branding data
    """
    doc = SimpleDocTemplate(output_path, pagesize=A4,
                            leftMargin=MARGIN, rightMargin=MARGIN,
                            topMargin=MARGIN, bottomMargin=MARGIN)
    story = _header_block(meta, school=school)

    # Subjects table — columns sum to CONTENT_W (180 mm)
    # 90 + 30 + 30 + 30 = 180
    subj_col_w = [90*mm, 30*mm, 30*mm, 30*mm]
    rows = [["SUBJECTS", "CLASSWORK", "TEST (%)", "CLASS AVE. (%)"]]
    for s in subjects:
        rows.append([
            Paragraph(s["name"], S["cell"]),
            s.get("classwork", ""),
            str(s["test_pct"])       if s.get("test_pct")       is not None else "-",
            str(s["class_avg_pct"]) if s.get("class_avg_pct") is not None else "-",
        ])
    subj_tbl = Table(rows, colWidths=subj_col_w, repeatRows=1)
    subj_tbl.setStyle(_base_table_style(font_size=8.5))
    story.append(subj_tbl)
    story.append(Spacer(1, 4 * mm))

    def _side_table(title, data_dict, keys):
        rows = [[title, meta.get("term", "")]] + [[k, data_dict.get(k, "")] for k in keys]
        return _mini_table(rows, [INNER_LABEL, INNER_VALUE])

    # Homework + Project Work
    story.append(_wrapper(
        _side_table("HOMEWORK",     homework,     ["Submission","Presentation","Effort"]),
        _side_table("PROJECT WORK", project_work, ["Submission","Presentation","Effort"]),
    ))
    story.append(Spacer(1, 3 * mm))

    # Clubs + Sports (using default INNER_TABLE_W width)
    story.append(_wrapper(
        _list_table("CLUBS",  clubs),
        _list_table("SPORTS", sports),
    ))
    story.append(Spacer(1, 3 * mm))

    # Other (full width)
    if other:
        story.append(_list_table("OTHER", other, CONTENT_W))
        story.append(Spacer(1, 3 * mm))

    # Attendance + grade scale
    gs = grade_scale or {
        "A": {"min": 80, "desc": "Very Good"},
        "B": {"min": 60, "desc": "Good"},
        "C": {"min": 50, "desc": "Satisfactory"},
        "D": {"min":  0, "desc": "Weak"},
    }
    att_rows = [["Attendance",          meta.get("term", "")],
                ["No. of days present", str(attendance.get("present", ""))],
                ["No. of days absent",  str(attendance.get("absent",  ""))]]
    story.append(_wrapper(
        _mini_table(att_rows, [INNER_LABEL, INNER_VALUE]),
        _grade_scale_table(gs, HALF_W),
    ))
    story += _footer()
    doc.build(story)
    print(f"✔  Grade 1/2 report saved → {output_path}")


# ══════════════════════════════════════════════════════════════════════════════
# TEMPLATE 3 – Grade 7  (marks + grades + attainment + effort)
# ══════════════════════════════════════════════════════════════════════════════
def generate_grade7_report(meta: dict, subjects: list,
                            homework: dict, project_work: dict,
                            clubs: list, sports: list, other: list,
                            attendance: dict, grade_scale: dict,
                            output_path: str, school=None):
    """
    subjects – [{name, marks_pct, grade, class_avg_pct, attainment, effort}, …]
               marks_pct / class_avg_pct may be None
    school   – School model instance with branding data
    """
    doc = SimpleDocTemplate(output_path, pagesize=A4,
                            leftMargin=MARGIN, rightMargin=MARGIN,
                            topMargin=MARGIN, bottomMargin=MARGIN)
    story = _header_block(meta, school=school)

    # Subjects table — columns sum to CONTENT_W (180 mm)
    # 72 + 24 + 16 + 26 + 22 + 20 = 180
    col_w = [72*mm, 24*mm, 16*mm, 26*mm, 22*mm, 20*mm]
    exam_hdr = ["", "EXAMINATION/TEST", "", "", "TERM", ""]
    sub_hdr  = ["SUBJECTS", "MARKS (%)", "GRADE", "CLASS AV. (%)", "ATTAINMENT", "EFFORT"]
    rows = [exam_hdr, sub_hdr]
    for s in subjects:
        rows.append([
            Paragraph(s["name"], S["cell"]),
            str(s["marks_pct"])      if s.get("marks_pct")      is not None else "-",
            s.get("grade", ""),
            str(s["class_avg_pct"]) if s.get("class_avg_pct") is not None else "-",
            s.get("attainment", ""),
            s.get("effort", ""),
        ])

    subj_tbl = Table(rows, colWidths=col_w, repeatRows=2)
    style = _base_table_style(font_size=8, header_rows=2)
    style.add("SPAN",       (1, 0), (3, 0))   # EXAMINATION/TEST
    style.add("SPAN",       (4, 0), (5, 0))   # TERM
    subj_tbl.setStyle(style)
    story.append(subj_tbl)
    story.append(Spacer(1, 4 * mm))

    def _side_table(title, data_dict, keys):
        rows = [[title, meta.get("term", "")]] + [[k, data_dict.get(k, "")] for k in keys]
        return _mini_table(rows, [INNER_LABEL, INNER_VALUE])

    story.append(_wrapper(
        _side_table("HOMEWORK",     homework,     ["Submission","Presentation","Effort"]),
        _side_table("PROJECT WORK", project_work, ["Submission","Presentation","Effort"]),
    ))
    story.append(Spacer(1, 3 * mm))

    # Clubs + Sports (using default INNER_TABLE_W width)
    story.append(_wrapper(
        _list_table("CLUBS",  clubs),
        _list_table("SPORTS", sports),
    ))
    story.append(Spacer(1, 3 * mm))

    if other:
        story.append(_list_table("OTHER", other, CONTENT_W))
        story.append(Spacer(1, 3 * mm))

    gs = grade_scale or {
        "A": {"min": 80, "desc": "Very Good"},
        "B": {"min": 60, "desc": "Good"},
        "C": {"min": 50, "desc": "Satisfactory"},
        "D": {"min": 40, "desc": "Weak"},
        "E": {"min":  0, "desc": "Very Weak"},
    }
    att_rows = [["Attendance",          meta.get("term", "")],
                ["No. of days present", str(attendance.get("present", ""))],
                ["No. of days absent",  str(attendance.get("absent",  ""))]]
    story.append(_wrapper(
        _mini_table(att_rows, [INNER_LABEL, INNER_VALUE]),
        _grade_scale_table(gs, HALF_W),
    ))
    story += _footer()
    doc.build(story)
    print(f"✔  Grade 7 report saved → {output_path}")


# ══════════════════════════════════════════════════════════════════════════════
# Demo – generates one sample PDF for each template
# ══════════════════════════════════════════════════════════════════════════════
if __name__ == "__main__":
    import argparse

    parser = argparse.ArgumentParser(
        description="Pinewood Preparatory School – Report Card Generator")
    parser.add_argument("template", nargs="?",
        choices=["beginners", "grade12", "grade7", "all"],
        default="all",
        help="Which template to generate (default: all)")
    parser.add_argument("--out-dir", default=".",
        help="Output directory (default: current directory)")
    args = parser.parse_args()
    os.makedirs(args.out_dir, exist_ok=True)

    # ── Sample data ────────────────────────────────────────────────────────────
    META_BEGINNERS = {
        "name": "Bukata Kalipinde", "class": "B - 1 2023", "admn": "PW566",
        "age": "3", "avg_age": "2", "teachers": "Monje Musenga, Christine Ngoma",
        "term": "TERM 1 2023", "next_term": "08/05/2023",
    }

    SKILLS_SAMPLE = {
        "Walks, runs and jumps easily.":           "GOOD",
        "Can throw a ball to a partner.":          "BEGINNING",
        "Can catch a ball.":                        "BEGINNING",
        "Can climb stairs without hands.":          "SATISFACTORY",
        "Holds pencil, crayon etc. correctly.":    "NOT YET",
        "Can cut with scissors.":                   "NOT YET",
        "Can manipulate small objects.":            "NOT YET",
        "Can pour water without spilling.":         "NOT YET",
        "Can complete a simple inset puzzle.":      "NOT YET",
        "Does simple interlocking jigsaw.":         "NOT YET",
        "Can recognise and match colours.":         "BEGINNING",
        "Recognises main shapes.":                  "BEGINNING",
        "Can sort objects into groups on basis of common feature e.g. colour.": "NOT YET",
        "Can match on one-to-one basis e.g. a cup to each saucer.": "NOT YET",
        "Counts objects up to ten.":                "NOT YET",
        "Counts objects up to twenty.":             "NOT YET",
        "Can write numbers up to 10.":              "NOT YET",
        "Can recognise letters A – Z.":             "BEGINNING",
        "Can write letters A – Z.":                 "NOT YET",
        "Can recognise own name.":                  "NOT YET",
        "Knows different lengths of time.":         "NOT YET",
        "Knows about more or less in volume, weight and quantity.": "NOT YET",
        "Understands conservation of volume.":      "NOT YET",
        "Can recognise a familiar melody.":         "NOT YET",
        "Speaks clearly – can be understood.":      "BEGINNING",
        "Uses sentence of 5 words +.":              "NOT YET",
        "Asks questions demanding explanations.":   "NOT YET",
        "Can answer questions correctly.":          "BEGINNING",
        "Can express ideas clearly.":               "BEGINNING",
        "Can write own name.":                      "NOT YET",
        "Can carry a message correctly.":           "NOT YET",
        "Shows interest in stories.":               "SATISFACTORY",
        "Shows interest in books.":                 "BEGINNING",
        "Participates in dramatic activities.":     "BEGINNING",
        "Can recite 12 or more nursery rhymes or songs.": "BEGINNING",
        "Makes representational drawings.":         "NOT YET",
        "Paints scenes and can talk about them.":   "NOT YET",
        "Uses clay to make recognisable objects.":  "NOT YET",
        "Uses material in individual ways.":        "BEGINNING",
        "Plays imaginatively e.g. with blocks.":    "BEGINNING",
        "Appreciates others' creative work.":       "NOT YET",
        "Likes to be independent.":                 "BEGINNING",
        "Plays alongside other children.":          "BEGINNING",
        "Plays with other children.":               "BEGINNING",
        "Joins in group activities.":               "SATISFACTORY",
        "Shares with other children.":              "BEGINNING",
        "Co-operates with adults.":                 "BEGINNING",
        "Knows how to greet strangers.":            "BEGINNING",
        "Willing to help with jobs e.g. tidying up.": "BEGINNING",
        "Can concentrate on a chosen activity for 5 minutes.":  "SATISFACTORY",
        "Can concentrate on a chosen activity for 10 minutes.": "BEGINNING",
        "Can concentrate on a chosen activity for 15 minutes.": "NOT YET",
        "Usually completes activities.":            "BEGINNING",
        "Will persist with things found difficult.": "NOT YET",
        "Able to listen to short passages of music.": "SATISFACTORY",
    }

    META_G12 = {
        "name": "Abigail Hamanyati", "class": "G1 - A 2023", "admn": "PW139",
        "age": "7 years 1 month", "avg_age": "6",
        "teachers": "Kampamba Mulenga, Daisy Kapapa",
        "term": "TERM 2 2023", "next_term": "04/09/2023",
    }

    G12_SUBJECTS = [
        {"name":"English - Reading and Comprehension","classwork":"B","test_pct":91,"class_avg_pct":90},
        {"name":"English - Spelling and Writing",      "classwork":"B","test_pct":75,"class_avg_pct":86},
        {"name":"Mathematics",          "classwork":"B","test_pct":90,"class_avg_pct":86},
        {"name":"Science",              "classwork":"A","test_pct":93,"class_avg_pct":86},
        {"name":"Social Studies",       "classwork":"B","test_pct":77,"class_avg_pct":83},
        {"name":"Geography",            "classwork":"B","test_pct":63,"class_avg_pct":81},
        {"name":"French",               "classwork":"A","test_pct":100,"class_avg_pct":71},
        {"name":"Religious Education",  "classwork":"B","test_pct":87,"class_avg_pct":83},
        {"name":"Information Technology","classwork":"C","test_pct":90,"class_avg_pct":85},
        {"name":"Verbal Reasoning",     "classwork":"B","test_pct":97,"class_avg_pct":87},
        {"name":"Non-Verbal Reasoning", "classwork":"B","test_pct":64,"class_avg_pct":93},
        {"name":"Art & Craft",          "classwork":"B","test_pct":60,"class_avg_pct":71},
        {"name":"Music",                "classwork":"B","test_pct":62,"class_avg_pct":72},
        {"name":"Physical Education",   "classwork":"A","test_pct":None,"class_avg_pct":None},
    ]

    META_G7 = {
        "name": "Bertha Taonga Chanda", "class": "G7 - A 2023", "admn": "PW501",
        "age": "12 years 4 months", "avg_age": "12",
        "teachers": "Jacob Nyirenda",
        "term": "TERM 2 2023", "next_term": "04/09/2023",
    }

    G7_SUBJECTS = [
        {"name":"English",        "marks_pct":90,"grade":"A","class_avg_pct":90,"attainment":"A","effort":"A"},
        {"name":"Mathematics",    "marks_pct":93,"grade":"A","class_avg_pct":86,"attainment":"A","effort":"A"},
        {"name":"Social Studies", "marks_pct":93,"grade":"A","class_avg_pct":85,"attainment":"A","effort":"A"},
        {"name":"Science",        "marks_pct":96,"grade":"A","class_avg_pct":85,"attainment":"A","effort":"A"},
        {"name":"CTS - Examination","marks_pct":90,"grade":"A","class_avg_pct":82,"attainment":"-","effort":"-"},
        {"name":"CTS - Home Economics","marks_pct":None,"grade":"-","class_avg_pct":0,"attainment":"A","effort":"A"},
        {"name":"CTS - Technology Studies","marks_pct":89,"grade":"A","class_avg_pct":82,"attainment":"A","effort":"A"},
        {"name":"CTS - Music (Expressive Arts)","marks_pct":87,"grade":"A","class_avg_pct":79,"attainment":"A","effort":"A"},
        {"name":"CTS - Art (Expressive Arts)","marks_pct":62,"grade":"B","class_avg_pct":66,"attainment":"B","effort":"B"},
        {"name":"CTS - Physical Education (Expressive Arts)","marks_pct":None,"grade":"B","class_avg_pct":None,"attainment":"B","effort":"B"},
        {"name":"Verbal Reasoning","marks_pct":100,"grade":"A","class_avg_pct":95,"attainment":"A","effort":"A"},
        {"name":"Non-Verbal Reasoning","marks_pct":96,"grade":"A","class_avg_pct":96,"attainment":"A","effort":"A"},
        {"name":"French",         "marks_pct":59,"grade":"C","class_avg_pct":57,"attainment":"B","effort":"B"},
    ]

    HW  = {"Submission": "Good",      "Presentation": "Good",      "Effort": "Very Good"}
    PW  = {"Submission": "Very Good", "Presentation": "Good",      "Effort": "Very Good"}
    HW7 = {"Submission": "Very Good", "Presentation": "Very Good", "Effort": "Very Good"}
    PW7 = {"Submission": "Very Good", "Presentation": "Very Good", "Effort": "Very Good"}

    if args.template in ("beginners", "all"):
        generate_beginners_report(
            meta=META_BEGINNERS,
            skills_data=SKILLS_SAMPLE,
            project_work={"Submission":"Good","Presentation":"Average","Effort":"Good"},
            attendance={"present": 50, "absent": 9},
            output_path=os.path.join(args.out_dir, "sample_beginners_report.pdf"),
        )

    if args.template in ("grade12", "all"):
        generate_grade12_report(
            meta=META_G12, subjects=G12_SUBJECTS,
            homework=HW, project_work=PW,
            clubs=["Computers","Drama","Literacy","Mathematics"],
            sports=["Athletics","Basketball","Soccer"],
            other=["Spelling Competition","Handwriting Competition"],
            attendance={"present": 57, "absent": 1},
            grade_scale=None,
            output_path=os.path.join(args.out_dir, "sample_grade12_report.pdf"),
        )

    if args.template in ("grade7", "all"):
        generate_grade7_report(
            meta=META_G7, subjects=G7_SUBJECTS,
            homework=HW7, project_work=PW7,
            clubs=["Chess","Debate"],
            sports=["Basketball","Hockey","Netball","Volleyball"],
            other=["ISAZ Chess","Handwriting Competition","Spelling Competition"],
            attendance={"present": 57, "absent": 1},
            grade_scale=None,
            output_path=os.path.join(args.out_dir, "sample_grade7_report.pdf"),
        )
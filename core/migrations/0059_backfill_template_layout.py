from django.db import migrations


def backfill_template_layout(apps, schema_editor):
    """
    Fix existing ReportTemplate records that all defaulted to FULL_ACADEMIC.

    Priority order:
    1. Template has a grading scale with a non-empty report_layout → use that.
    2. No grading scale (or scale has no layout set) → derive from course name.
    """
    ReportTemplate = apps.get_model('core', 'ReportTemplate')

    # 1. Fix via grading scale's report_layout
    ReportTemplate.objects.filter(
        grading_scale__report_layout='SKILLS',
    ).exclude(layout_type='SKILLS').update(layout_type='SKILLS')

    ReportTemplate.objects.filter(
        grading_scale__report_layout='SIMPLE_ACADEMIC',
    ).exclude(layout_type='SIMPLE_ACADEMIC').update(layout_type='SIMPLE_ACADEMIC')

    # 2. Fix remaining FULL_ACADEMIC templates with no grading scale using course name
    SKILLS_KEYWORDS = ('RECEPTION', 'BEGINNERS', 'MIDDLE CLASS', 'NURSERY', 'PRE-SCHOOL', 'PREP', 'KINDERGARTEN', 'KG')
    SIMPLE_KEYWORDS = ('GRADE 1', 'GRADE 2', 'YEAR 1', 'YEAR 2', 'STD 1', 'STD 2', 'CLASS 1', 'CLASS 2')

    remaining = ReportTemplate.objects.filter(
        grading_scale__isnull=True,
        layout_type='FULL_ACADEMIC',
    ).select_related('batch__course')

    skills_ids, simple_ids = [], []
    for tmpl in remaining:
        try:
            name_upper = tmpl.batch.course.course_name.upper()
        except Exception:
            continue
        if any(kw in name_upper for kw in SKILLS_KEYWORDS):
            skills_ids.append(tmpl.pk)
        elif any(kw in name_upper for kw in SIMPLE_KEYWORDS):
            simple_ids.append(tmpl.pk)

    if skills_ids:
        ReportTemplate.objects.filter(pk__in=skills_ids).update(layout_type='SKILLS')
    if simple_ids:
        ReportTemplate.objects.filter(pk__in=simple_ids).update(layout_type='SIMPLE_ACADEMIC')

    # 3. Also fix templates whose grading scale has no report_layout set — use course name
    no_layout_qs = ReportTemplate.objects.filter(
        grading_scale__report_layout='',
        layout_type='FULL_ACADEMIC',
    ).select_related('batch__course')

    skills_ids2, simple_ids2 = [], []
    for tmpl in no_layout_qs:
        try:
            name_upper = tmpl.batch.course.course_name.upper()
        except Exception:
            continue
        if any(kw in name_upper for kw in SKILLS_KEYWORDS):
            skills_ids2.append(tmpl.pk)
        elif any(kw in name_upper for kw in SIMPLE_KEYWORDS):
            simple_ids2.append(tmpl.pk)

    if skills_ids2:
        ReportTemplate.objects.filter(pk__in=skills_ids2).update(layout_type='SKILLS')
    if simple_ids2:
        ReportTemplate.objects.filter(pk__in=simple_ids2).update(layout_type='SIMPLE_ACADEMIC')


def noop(apps, schema_editor):
    pass


class Migration(migrations.Migration):

    dependencies = [
        ('core', '0058_examscore_grade_value'),
    ]

    operations = [
        migrations.RunPython(backfill_template_layout, noop),
    ]

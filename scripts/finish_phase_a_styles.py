#!/usr/bin/env python3
"""Remove inline <style> blocks from Phase A (PARTIAL) gradebook templates."""

import re
from pathlib import Path

PROJECT_ROOT = Path(__file__).parent.parent
TEMPLATES_DIR = PROJECT_ROOT / "templates" / "core" / "gradebook"

# All 17 gradebook Phase A PARTIAL files
PHASE_A_GRADEBOOK = [
    "grading_settings.html",
    "gradebook_management.html",
    "exam_planners_list.html",
    "exam_plan_detail.html",
    "exam_group_marks_entry.html",
    "enhanced_score_entry.html",
    "single_exam_marks_entry.html",
    "comprehensive_reports.html",
    "create_exam.html",
    "create_exam_plan.html",
    "edit_term_exam.html",
    "bulk_skills_assessment.html",
    "class_exam_planner.html",
    "manage_exam_plan_classes.html",
    "skills_assessment_reports.html",
    "skills_category_view.html",
    "skills_progress_tracking.html",
]

def remove_style_block(content):
    """Remove entire {% block extra_css %} ... {% endblock %} or <style>...</style>."""
    # Try to remove {% block extra_css %} ... {% endblock %} first
    content = re.sub(
        r"{% block extra_css %}\s*\n<style>.*?</style>\s*\n{% endblock %}\n",
        "",
        content,
        flags=re.DOTALL
    )
    # Then try bare <style>...</style> blocks (in extra_css or not)
    content = re.sub(
        r"<style>.*?</style>\s*\n?",
        "",
        content,
        flags=re.DOTALL
    )
    return content

def main():
    count = 0
    for filename in PHASE_A_GRADEBOOK:
        filepath = TEMPLATES_DIR / filename
        if not filepath.exists():
            print(f"  SKIP {filename} (not found)")
            continue

        with open(filepath, "r", encoding="utf-8") as f:
            original = f.read()

        modified = remove_style_block(original)

        if modified != original:
            with open(filepath, "w", encoding="utf-8") as f:
                f.write(modified)
            style_count_before = original.count("<style")
            style_count_after = modified.count("<style")
            print(f"  OK {filename} ({style_count_before} -> {style_count_after} <style blocks)")
            count += 1
        else:
            print(f"  -- {filename} (no change)")

    print(f"\n[DONE] Processed {count}/{len(PHASE_A_GRADEBOOK)} files")

if __name__ == "__main__":
    main()

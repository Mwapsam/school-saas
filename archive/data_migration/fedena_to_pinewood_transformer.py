#!/usr/bin/env python3
"""
Fedena to Pinewood Data Transformation Script

This script transforms data from Fedena MySQL dump to Pinewood PostgreSQL database
with proper field mappings, data conversion, and tenant-aware structure.

Usage:
    python fedena_to_pinewood_transformer.py [--dry-run] [--table TABLE_NAME] [--tenant-id TENANT_ID]
"""

from dataclasses import field
import os
import re
import sys
import uuid
import psycopg2
from psycopg2.extras import execute_values
import mysql.connector
import argparse
from pathlib import Path
from typing import List, Dict, Optional, Any, Tuple
from datetime import datetime, date, timedelta
from decimal import Decimal


class FedenaTableMapping:
    """Configuration for mapping Fedena tables to Pinewood models."""

    FIELD_MAPPINGS = {
        "academic_years": {
            "target_model": "core_academicyear",
            "fields": {
                "id": {"target": "id", "transform": "fedena_id_to_uuid"},
                "name": {"target": "name"},
                "start_date": {"target": "start_date"},
                "end_date": {"target": "end_date"},
                "is_active": {"target": "is_active", "transform": "mysql_bool_to_pg"},
                "created_at": {"target": "created_at"},
                "updated_at": {"target": "updated_at"},
            },
            "tenant_field": True,
            "dependencies": [],
        },
        "courses": {
            "target_model": "core_course",
            "fields": {
                "id": {"target": "id", "transform": "fedena_id_to_uuid"},
                "course_name": {
                    "target": "course_name"
                },  # Fix: map to course_name not name
                "code": {"target": "code"},
                "section_name": {"target": "section_name"},
                "grading_type": {"target": "grading_type"},
                "is_deleted": {"target": "is_deleted", "transform": "mysql_bool_to_pg", "default": False},
                "created_at": {"target": "created_at"},
                "updated_at": {"target": "updated_at"},
            },
            "tenant_field": True,
            "dependencies": [],
            "filters": [
                "is_deleted = 0 OR is_deleted = 1",
                "id IN (SELECT MIN(id) FROM courses GROUP BY code)"
            ],
        },
        "elective_groups": {
            # Placeholder mapping - table exists but has no data
            "target_model": None,  # No target model needed
            "skip_if_empty": True,
            "fields": {},
        },
        "batches": {
            "target_model": "core_batch",
            "fields": {
                "id": {"target": "id", "transform": "fedena_id_to_uuid"},
                "name": {"target": "name"},
                "course_id": {
                    "target": "course_id",
                    "transform": "fedena_id_to_uuid",
                },  # ADD THIS
                "academic_year_id": {
                    "target": "academic_year_id",
                    "transform": "fedena_id_to_uuid",
                },  # ADD THIS
                "start_date": {"target": "start_date"},
                "end_date": {"target": "end_date"},
                "is_active": {"target": "is_active", "transform": "mysql_bool_to_pg"},
                "is_deleted": {"target": "is_deleted", "transform": "mysql_bool_to_pg", "default": False},
                "class_teacher_id": {
                    "target": "employee_id",
                    "transform": "fedena_id_to_uuid",
                },  # Fedena stores class teacher in class_teacher_id (int FK), not employee_id (varchar, always NULL)
                "created_at": {"target": "created_at"},
                "updated_at": {"target": "updated_at"},
            },
            "tenant_field": True,
            "dependencies": ["courses", "academic_years", "employees"],
            "filters": [
                "is_deleted = 0 OR is_deleted IS NULL",
            ],
        },
        "students": {
            "target_model": "core_student",
            "fields": {
                "id": {"target": "id", "transform": "fedena_id_to_uuid"},
                "admission_no": {"target": "admission_no"},
                "admission_date": {"target": "admission_date"},
                "class_roll_no": {"target": "class_roll_no"},
                "first_name": {"target": "first_name"},
                "middle_name": {"target": "middle_name"},
                "last_name": {"target": "last_name"},
                "date_of_birth": {"target": "date_of_birth"},
                "gender": {"target": "gender", "transform": "gender_to_full"},
                "blood_group": {"target": "blood_group"},
                "birth_place": {"target": "birth_place"},
                "language": {"target": "language"},
                "religion": {"target": "religion"},
                "address_line1": {"target": "address_line1"},
                "address_line2": {"target": "address_line2"},
                "city": {"target": "city"},
                "state": {"target": "state"},
                "pin_code": {"target": "pin_code"},
                "phone1": {"target": "phone1"},
                "phone2": {"target": "phone2"},
                "email": {"target": "email"},
                "is_sms_enabled": {
                    "target": "is_sms_enabled",
                    "transform": "mysql_bool_to_pg",
                    "default": False,
                },
                "status_description": {"target": "status_description"},
                "is_active": {"target": "is_active", "transform": "mysql_bool_to_pg"},
                "is_deleted": {"target": "is_deleted", "transform": "mysql_bool_to_pg", "default": False},
                "created_at": {"target": "created_at"},
                "updated_at": {"target": "updated_at"},
            },
            "tenant_field": True,
            "dependencies": [],
            # admission_no is globally unique in core_student — keep the lowest-id
            # source row per admission_no so a second row can't silently fail insert.
            "dedupe_key": "admission_no",
        },
        "employees": {
            "target_model": "core_employee",
            "fields": {
                "id": {"target": "id", "transform": "fedena_id_to_uuid"},
                "employee_number": {"target": "employee_number"},
                "first_name": {"target": "first_name"},
                "middle_name": {"target": "middle_name"},
                "last_name": {"target": "last_name"},
                "gender": {"target": "gender", "transform": "gender_to_bool"},
                "date_of_birth": {"target": "date_of_birth"},
                "joining_date": {"target": "joining_date"},
                "job_title": {"target": "job_title"},
                "qualification": {"target": "qualification"},
                "phone": {"target": "mobile_phone"},
                "email": {"target": "email"},
                "is_active": {"target": "is_active", "transform": "mysql_bool_to_pg"},
                "status": {"target": "status", "transform": "mysql_bool_to_pg"},
                "created_at": {"target": "created_at"},
                "updated_at": {"target": "updated_at"},
            },
            "tenant_field": True,
            "dependencies": [],
            "filters": [],
            # employee_number is globally unique in core_employee.
            "dedupe_key": "employee_number",
        },
        "employee_departments": {
            "target_model": "core_employeedepartment",
            "fields": {
                "id": {"target": "id", "transform": "fedena_id_to_uuid"},
                "name": {"target": "name"},
                "code": {"target": "code"},
                "status": {"target": "status", "transform": "mysql_bool_to_pg"},
                "created_at": {"target": "created_at"},
                "updated_at": {"target": "updated_at"},
            },
            "tenant_field": True,
            "dependencies": [],
        },
        "employee_positions": {
            "target_model": "core_employeeposition",
            "fields": {
                "id": {"target": "id", "transform": "fedena_id_to_uuid"},
                "name": {"target": "name"},
                "employee_category_id": {"target": "employee_category_id", "transform": "fedena_id_to_uuid"},
                "status": {"target": "status", "transform": "mysql_bool_to_pg"},
                "created_at": {"target": "created_at"},
                "updated_at": {"target": "updated_at"},
            },
            "tenant_field": True,
            "dependencies": ["employee_categories"],
        },
        "employee_categories": {
            "target_model": "core_employeecategory",
            "fields": {
                "id": {"target": "id", "transform": "fedena_id_to_uuid"},
                "name": {"target": "name"},
                "prefix": {"target": "prefix"},
                "status": {"target": "status", "transform": "mysql_bool_to_pg"},
                "created_at": {"target": "created_at"},
                "updated_at": {"target": "updated_at"},
            },
            "tenant_field": True,
            "dependencies": [],
        },
        "employee_grades": {
            "target_model": "core_employeegrade",
            "fields": {
                "id": {"target": "id", "transform": "fedena_id_to_uuid"},
                "name": {"target": "name"},
                "priority": {"target": "priority"},
                "max_hours_day": {"target": "max_hours_day"},
                "max_hours_week": {"target": "max_hours_week"},
                "status": {
                    "target": "status",
                    "transform": "mysql_bool_to_pg",
                },  # Fix: map to 'status' not 'is_active'
                "created_at": {"target": "created_at"},
                "updated_at": {"target": "updated_at"},
            },
            "tenant_field": True,
            "dependencies": [],
        },
        "student_categories": {
            "target_model": "core_studentcategory",
            "fields": {
                "id": {"target": "id", "transform": "fedena_id_to_uuid"},
                "name": {"target": "name"},
                "is_deleted": {"target": "is_deleted", "transform": "mysql_bool_to_pg", "default": False},
                "created_at": {"target": "created_at"},
                "updated_at": {"target": "updated_at"},
            },
            "tenant_field": True,
            "dependencies": [],
        },
        "subjects": {
            "target_model": "core_subject",
            "fields": {
                "id": {"target": "id", "transform": "fedena_id_to_uuid"},
                "name": {"target": "name"},
                "code": {"target": "code"},
                "batch_id": {"target": "batch_id", "transform": "fedena_id_to_uuid"},
                "max_weekly_classes": {"target": "max_weekly_classes"},
                # elective_groups are not migrated (no target model), so always null this FK
                "elective_group_id": {"target": "elective_group_id", "default": None},
                "is_deleted": {"target": "is_deleted", "transform": "mysql_bool_to_pg", "default": False},
                "created_at": {"target": "created_at"},
                "updated_at": {"target": "updated_at"},
            },
            "tenant_field": True,
            # removed "elective_groups" dependency — it has no target model and creates nothing
            "dependencies": ["batches"],
            "default_values": {
                "no_exams": False,
                "language": False,
                "prefer_consecutive": False,
            },
        },
        # Many-to-Many Relationships
        "batch_students": {
            "target_model": "core_batchstudent",
            "fields": {
                "id": {"target": "id", "transform": "fedena_id_to_uuid"},
                "student_id": {
                    "target": "student_id",
                    "transform": "fedena_id_to_uuid",
                },
                "batch_id": {"target": "batch_id", "transform": "fedena_id_to_uuid"},
                "roll_number": {"target": "roll_number"},
                "created_at": {"target": "created_at"},
                "updated_at": {"target": "updated_at"},
            },
            "tenant_field": True,
            "dependencies": ["students", "batches"],
            "filters": ["student_id IS NOT NULL", "batch_id IS NOT NULL"],
        },
        "guardians": {
            "target_model": "core_guardian",
            "fields": {
                "id": {"target": "id", "transform": "fedena_id_to_uuid"},
                "first_name": {"target": "first_name"},
                "last_name": {"target": "last_name"},
                "relation": {
                    "target": "relation",
                    "default": "Parent",
                },  # Default if missing
                "mobile_phone": {"target": "mobile_phone"},
                "email": {"target": "email"},
                "city": {"target": "city"},
                "state": {"target": "state"},
                "created_at": {"target": "created_at"},
                "updated_at": {"target": "updated_at"},
            },
            "tenant_field": True,
            "dependencies": [],
        },
        "guardians_as_relations": {
            "target_model": "core_studentguardianrelation",
            "fields": {
                "ward_id": {"target": "student_id", "transform": "fedena_id_to_uuid"},
                "id": {"target": "guardian_id", "transform": "fedena_id_to_uuid"},
                "relation": {"target": "relation"},
                "created_at": {"target": "created_at"},
                "updated_at": {"target": "updated_at"},
            },
            "tenant_field": True,
            "dependencies": ["students", "guardians"],
            "source_table": "guardians",  # Actually read from guardians table
        },
        "weekday_sets": {
            "target_model": "core_weekday",
            "fields": {
                "id": {"target": "id", "transform": "fedena_id_to_uuid"},
                "created_at": {"target": "created_at"},
                "updated_at": {"target": "updated_at"},
            },
            "default_values": {
                "weekday": "Monday",  # Default weekday name since source doesn't have name field
                "day_of_week": 1,  # Monday = 1
            },
            "tenant_field": True,
            "dependencies": [],
        },
        "class_timings": {
            "target_model": "core_classtiming",
            "fields": {
                "id": {"target": "id", "transform": "fedena_id_to_uuid"},
                "name": {"target": "name"},
                "start_time": {"target": "start_time"},
                "end_time": {"target": "end_time"},
                "is_break": {"target": "is_break", "transform": "mysql_bool_to_pg", "default": False},
                "is_deleted": {"target": "is_deleted", "transform": "mysql_bool_to_pg", "default": False},
                "created_at": {"target": "created_at"},
                "updated_at": {"target": "updated_at"},
            },
            "tenant_field": True,
            "dependencies": [],
            "filters": [],  # Re-enabled with bulletproof defaults
        },
        "timetables": {
            "target_model": "core_timetable",
            "fields": {
                "id": {"target": "id", "transform": "fedena_id_to_uuid"},
                "batch_id": {"target": "batch_id", "transform": "fedena_id_to_uuid"},
                "subject_id": {
                    "target": "subject_id",
                    "transform": "fedena_id_to_uuid",
                },
                "employee_id": {
                    "target": "employee_id",
                    "transform": "fedena_id_to_uuid",
                },
                "weekday_id": {
                    "target": "weekday_id",
                    "transform": "fedena_id_to_uuid",
                },
                "class_timing_id": {
                    "target": "class_timing_id",
                    "transform": "fedena_id_to_uuid",
                },
                "created_at": {"target": "created_at"},
                "updated_at": {"target": "updated_at"},
            },
            "tenant_field": True,
            "dependencies": [
                "batches",
                "subjects",
                "employees",
                "weekday_sets",
                "class_timings",
            ],
        },
        # =================================================================
        # HIGH-PRIORITY ACADEMIC TABLES
        # =================================================================
        "exams": {
            "target_model": "core_exam",
            "fields": {
                "id": {"target": "id", "transform": "fedena_id_to_uuid"},
                "exam_group_id": {
                    "target": "exam_group_id",
                    "transform": "fedena_id_to_uuid",
                },
                "subject_id": {
                    "target": "subject_id",
                    "transform": "fedena_id_to_uuid",
                },
                "start_time": {"target": "start_time"},
                "end_time": {"target": "end_time"},
                "maximum_marks": {"target": "maximum_marks"},
                "minimum_marks": {"target": "minimum_marks"},
                "grading_level_id": {
                    "target": "grading_level_id",
                    "transform": "fedena_id_to_uuid",
                },
                "weightage": {"target": "weightage", "transform": "to_int"},
                "created_at": {"target": "created_at"},
                "updated_at": {"target": "updated_at"},
            },
            "tenant_field": True,
            "dependencies": ["subjects", "exam_groups", "grading_levels"],
            "default_values": {
                "weightage": 0,
            },
        },
        "exam_groups": {
            "target_model": "core_examgroup",
            "fields": {
                "id": {"target": "id", "transform": "fedena_id_to_uuid"},
                "name": {"target": "name"},
                "batch_id": {"target": "batch_id", "transform": "fedena_id_to_uuid"},
                "exam_date": {"target": "exam_date"},
                "exam_type": {"target": "exam_type"},
                "is_published": {
                    "target": "is_published",
                    "transform": "mysql_bool_to_pg",
                },
                "result_published": {
                    "target": "result_published",
                    "transform": "mysql_bool_to_pg",
                },
                "is_final_exam": {
                    "target": "is_final_exam",
                    "transform": "mysql_bool_to_pg",
                },
                "created_at": {"target": "created_at"},
                "updated_at": {"target": "updated_at"},
            },
            "tenant_field": True,
            "dependencies": ["batches"],
        },
        "grades": {
            "target_model": "core_gradingtype",
            "fields": {
                "id": {"target": "id", "transform": "fedena_id_to_uuid"},
                "name": {"target": "name"},
                "description": {"target": "description"},
                "created_at": {"target": "created_at"},
                "updated_at": {"target": "updated_at"},
            },
            "tenant_field": True,
            "dependencies": [],
            "default_values": {
                "is_active": True,  # Default active status
                "gpa_scale": 10.0,  # Common Indian grading scale (10-point)
                "cce_scholastic_weight": 70.00,  # CCE scholastic weight
                "cce_coscholastic_weight": 30.00,  # CCE co-scholastic weight
            },
        },
        "grading_levels": {
            "target_model": "core_gradinglevel",
            "fields": {
                "id": {"target": "id", "transform": "fedena_id_to_uuid"},
                "name": {"target": "name"},
                "batch_id": {"target": "batch_id", "transform": "fedena_id_to_uuid"},
                "min_score": {"target": "min_score"},
                "max_score": {"target": "max_score"},
                # GradingLevel.is_deleted maps directly from source is_deleted
                "is_deleted": {"target": "is_deleted", "transform": "mysql_bool_to_pg", "default": False},
                "created_at": {"target": "created_at"},
                "updated_at": {"target": "updated_at"},
            },
            "tenant_field": True,
            "dependencies": ["batches"],
            "default_values": {
                "order": 0,    # required integer, no source equivalent
                "is_fail": False,  # required boolean, no source equivalent
            },
        },
        "attendances": {
            "target_model": "core_attendance",
            "fields": {
                "id": {"target": "id", "transform": "fedena_id_to_uuid"},
                "student_id": {
                    "target": "student_id",
                    "transform": "fedena_id_to_uuid",
                },
                "batch_id": {"target": "batch_id", "transform": "fedena_id_to_uuid"},
                "month_date": {"target": "month_date"},
                "forenoon": {"target": "forenoon", "transform": "mysql_bool_to_pg"},
                "afternoon": {"target": "afternoon", "transform": "mysql_bool_to_pg"},
                "reason": {"target": "reason"},
                "created_at": {"target": "created_at"},
                "updated_at": {"target": "updated_at"},
            },
            "default_values": {
                # period_table_entry is nullable (migrated via 0043) — Fedena attendance
                # has no per-period context, so we leave it NULL for migrated records.
                "period_table_entry_id": None,
            },
            "filters": [
                "student_id IN (SELECT id FROM students)",
                "batch_id IN (SELECT id FROM batches)"
            ],
            "tenant_field": True,
            "dependencies": ["students", "batches"],
        },
        "attendance_labels": {
            "target_model": "core_attendancelabel",
            "fields": {
                "id": {"target": "id", "transform": "fedena_id_to_uuid"},
                "name": {"target": "name"},
                "code": {"target": "code"},
                "attendance_type": {"target": "is_considered_present", "transform": "attendance_type_to_bool"},
                # color_code doesn't exist in source, will use default
                "is_active": {"target": "is_active", "transform": "mysql_bool_to_pg"},
                "created_at": {"target": "created_at"},
                "updated_at": {"target": "updated_at"},
            },
            "tenant_field": True,
            "dependencies": [],
            "default_values": {
                "color_code": "#808080",  # Default color since source doesn't have this field
                "affects_attendance_percentage": True,  # Default value
                "order": 0,  # Default order
            },
            # AttendanceLabel.code is unique per tenant.
            "dedupe_key": "code",
        },
        "assessment_marks": {
            "target_model": "core_assessmentmark",
            "fields": {
                "id": {"target": "id", "transform": "fedena_id_to_uuid"},
                "student_id": {
                    "target": "student_id",
                    "transform": "fedena_id_to_uuid",
                },
                "assessment_id": {"target": "exam_id", "transform": "fedena_id_to_uuid"},
                "marks": {"target": "marks"},
                "is_absent": {"target": "is_absent", "transform": "mysql_bool_to_pg"},
                "grade": {"target": "grade"},
                "created_at": {"target": "created_at"},
                "updated_at": {"target": "updated_at"},
            },
            "tenant_field": True,
            "dependencies": ["students", "exams", "subjects"],
            "filters": [
                "student_id IS NOT NULL AND student_id IN (SELECT id FROM students WHERE is_deleted = 0 OR is_deleted IS NULL)",
                "assessment_id IS NOT NULL AND assessment_id IN (SELECT id FROM exams WHERE is_deleted = 0 OR is_deleted IS NULL)",
            ],
            "batch_size": 1000,  # Process in batches of 1000 for efficiency
            "default_values": {
                "assessment_name": "Migrated Assessment",
                "assessment_type": "SUMMATIVE",
            },
        },
        "assignments": {
            "target_model": "core_assignment",
            "fields": {
                "id": {"target": "id", "transform": "fedena_id_to_uuid"},
                "title": {"target": "title"},
                "content": {"target": "content"},
                "duedate": {"target": "due_date"},
                "subject_id": {
                    "target": "subject_id",
                    "transform": "fedena_id_to_uuid",
                },
                "employee_id": {
                    "target": "employee_id",
                    "transform": "fedena_id_to_uuid",
                },
                "is_active": {"target": "is_active", "transform": "mysql_bool_to_pg"},
                "created_at": {"target": "created_at"},
                "updated_at": {"target": "updated_at"},
            },
            "tenant_field": True,
            "dependencies": ["batches", "subjects", "employees"],
        },
        # NOTE: "exam_scores" mapping removed — the Fedena dump has no exam_scores
        # rows (0 INSERT statements), so it migrated nothing.
        "course_subjects": {
            "target_model": "core_coursesubject",
            "fields": {
                "id": {"target": "id", "transform": "fedena_id_to_uuid"},
                "course_id": {"target": "course_id", "transform": "fedena_id_to_uuid"},
                "name": {"target": "subject_id", "transform": "subject_name_to_uuid"},
                "created_at": {"target": "created_at"},
                "updated_at": {"target": "updated_at"},
            },
            "tenant_field": True,
            "dependencies": ["courses", "subjects"],
            "filters": [
                "is_deleted = 0 OR is_deleted IS NULL",
                "course_id IN (SELECT id FROM courses WHERE is_deleted = 0 OR is_deleted IS NULL)",
            ],
            "default_values": {
                "is_active": True,
            },
        },
        "employees_subjects": {
            "target_model": "core_employeesubject",
            "fields": {
                "id": {"target": "id", "transform": "fedena_id_to_uuid"},
                "employee_id": {"target": "employee_id", "transform": "fedena_id_to_uuid"},
                "subject_id": {"target": "subject_id", "transform": "fedena_id_to_uuid"},
                "created_at": {"target": "created_at"},
                "updated_at": {"target": "updated_at"},
            },
            "default_values": {
                "is_active": True,
            },
            "tenant_field": True,
            "dependencies": ["employees", "subjects"],
        },
        # NOTE: CCE grading mappings ("cce_grade_sets", "cce_grades") and the online
        # examination mappings ("online_exam_groups", "online_exam_questions",
        # "online_exam_options") were removed — the Fedena dump has no rows in any of
        # these source tables (0 INSERT statements), so they migrated nothing.
        # =================================================================
        # GRADEBOOK TEMPLATES AND REMARKS
        # =================================================================
        "gradebook_templates": {
            "target_model": "core_gradebooktemplate",
            "fields": {
                "id": {"target": "id", "transform": "fedena_id_to_uuid"},
                "name": {"target": "name"},
                "template": {"target": "configuration", "transform": "yaml_to_json"},
                "is_active": {"target": "is_active", "transform": "mysql_bool_to_pg"},
                "is_default": {"target": "is_default", "transform": "mysql_bool_to_pg"},
                "created_at": {"target": "created_at"},
                "updated_at": {"target": "updated_at"},
            },
            "tenant_field": True,
            "dependencies": [],
            "default_values": {
                "template_type": "CUSTOM",
                "description": "Migrated from Fedena gradebook template",
            },
        },
        # NOTE: "remark_banks" and "student_previous_subject_marks" mappings removed
        # — the Fedena dump has no rows in either source table (0 INSERT statements),
        # so they migrated nothing.
        # =================================================================
        # FINANCIAL MANAGEMENT TABLES
        # =================================================================
        "finance_transactions": {
            "target_model": "core_financetransaction",
            # Note: Source table has many fields not mapped due to target model limitations:
            # fine_amount, fine_included, finance_fees_id, batch_id, financial_year_id,
            # payment_mode, receipt_no, voucher_no, trans_type, tax_amount, tax_included, etc.
            "fields": {
                "id": {"target": "id", "transform": "fedena_id_to_uuid"},
                "title": {"target": "title"},
                "description": {"target": "description"},
                "amount": {"target": "amount"},
                "category_id": {
                    "target": "category_id",
                    "transform": "fedena_id_to_uuid",
                },
                "student_id": {
                    "target": "student_id",
                    "transform": "fedena_id_to_uuid",
                },
                "transaction_date": {"target": "transaction_date"},
                "created_at": {"target": "created_at"},
                "updated_at": {"target": "updated_at"},
            },
            "tenant_field": True,
            "dependencies": [
                "finance_transaction_categories",
                "students",
            ],
            # No student filter — financial records exist independently of student deletion status.
            # Filtering by active students leaves receipt_records orphaned.
            "filters": [],
        },
        "finance_transaction_categories": {
            "target_model": "core_financetransactioncategory",
            "fields": {
                "id": {"target": "id", "transform": "fedena_id_to_uuid"},
                "name": {"target": "name"},
                "description": {"target": "description"},
                "is_income": {"target": "is_income", "transform": "mysql_bool_to_pg"},
                "is_deleted": {"target": "is_active", "transform": "invert_mysql_bool"},
                "created_at": {"target": "created_at"},
                "updated_at": {"target": "updated_at"},
            },
            "tenant_field": True,
            "dependencies": [],
        },
        "finance_fees": {
            "target_model": "core_financefee",
            "fields": {
                "id": {"target": "id", "transform": "fedena_id_to_uuid"},
                "fee_collection_id": {
                    "target": "fee_category_id",
                    "transform": "fee_collection_to_category_id",
                },
                "student_id": {
                    "target": "student_id",
                    "transform": "fedena_id_to_uuid",
                },
                "balance": {"target": "balance"},
                "batch_id": {
                    "target": "batch_id",
                    "transform": "fedena_id_to_uuid",
                },
                "discount_amount": {"target": "discount_amount", "default": 0.0},
                "particular_total": {"target": "particular_total", "default": 0.0},
                "tax_amount": {"target": "tax_amount", "default": 0.0},
                "is_paid": {"target": "is_paid", "transform": "mysql_bool_to_pg", "default": False},
                "created_at": {"target": "created_at"},
                "updated_at": {"target": "updated_at"},
            },
            "tenant_field": True,
            "dependencies": [
                "finance_fee_categories",
                "finance_fee_collections",  # fee_collection_to_category_id transform reads core_feecollection
                "students",
            ],
            "filters": [
                "student_id IS NULL OR student_id IN (SELECT id FROM students WHERE is_deleted = 0 OR is_deleted IS NULL)",
            ],
        },
        "finance_fee_collections": {
            "target_model": "core_feecollection",
            "fields": {
                "id": {"target": "id", "transform": "fedena_id_to_uuid"},
                "name": {"target": "name"},
                "start_date": {"target": "start_date"},
                "end_date": {
                    "target": "end_date",
                    "default": "2024-12-31"
                },
                "due_date": {"target": "due_date"},
                "fee_category_id": {
                    "target": "fee_category_id",
                    "transform": "fedena_id_to_uuid",
                },
                "batch_id": {"target": "batch_id", "transform": "fedena_id_to_uuid"},
                "is_deleted": {"target": "is_active", "transform": "invert_mysql_bool"},
                "created_at": {"target": "created_at"},
                "updated_at": {"target": "updated_at"},
            },
            "tenant_field": True,
            "dependencies": ["finance_fee_categories", "batches"],
            # Include deleted collections — finance_fees/fee_transactions still reference them
            "filters": [],
        },
        "finance_fee_categories": {
            "target_model": "core_feecategory",
            "fields": {
                "id": {"target": "id", "transform": "fedena_id_to_uuid"},
                "name": {"target": "name"},
                "description": {"target": "description"},
                "is_deleted": {"target": "is_deleted", "transform": "mysql_bool_to_pg", "default": False},
                "created_at": {"target": "created_at"},
                "updated_at": {"target": "updated_at"},
            },
            "tenant_field": True,
            "dependencies": [],
            # Include deleted categories — fees still reference them
            "filters": [],
        },
        "fee_transactions": {
            # Fedena fee_transactions is a junction table (finance_fee_id + finance_transaction_id).
            # Maps to core_feetransaction which has: transaction_type, transaction_date, amount,
            # student_id, fee_category_id, reference_number, description.
            "target_model": "core_feetransaction",
            "fields": {
                "id": {"target": "id", "transform": "fedena_id_to_uuid"},
                "created_at": {"target": "created_at"},
                "updated_at": {"target": "updated_at"},
            },
            "custom_mappings": {
                "student_id": {
                    "source": "finance_fee_id",
                    "transform": "finance_fee_id_to_student_uuid",
                },
                "fee_category_id": {
                    "source": "finance_fee_id",
                    "transform": "finance_fee_id_to_category_uuid",
                },
                "amount": {
                    "source": "finance_transaction_id",
                    "transform": "finance_transaction_id_to_amount",
                },
                "transaction_date": {
                    "source": "finance_transaction_id",
                    "transform": "finance_transaction_id_to_date",
                },
            },
            "default_values": {
                "transaction_type": "FEE_PAYMENT",
                "amount": 0.0,
                "transaction_date": "2024-01-01",
            },
            "tenant_field": True,
            "dependencies": ["students", "finance_fees"],
            "filters": [],
        },
        # =================================================================
        # USER MANAGEMENT & AUTHENTICATION
        # =================================================================
        "users": {
            "target_model": "core_user",
            "fields": {
                "id": {"target": "id", "transform": "fedena_id_to_uuid"},
                "username": {"target": "username"},
                "first_name": {"target": "first_name"},
                "last_name": {"target": "last_name"},
                "email": {"target": "email"},
                "admin": {"target": "is_admin", "transform": "mysql_bool_to_pg"},
                "hashed_password": {"target": "password"},  # Map existing hashed password
                "created_at": {"target": "created_at"},
                "updated_at": {"target": "updated_at"},
            },
            "tenant_field": False,  # UserProfile handles tenant relationship differently
            "dependencies": [],
            "default_values": {
                "is_verified": True,  # Migrated users are verified by default
            },
        },
        "privileges": {
            "target_model": "core_privilege",
            "fields": {
                "id": {
                    "target": "id",
                    "transform": "fedena_id_to_uuid",
                },  # Map to primary key id
                "name": {"target": "name"},
                "is_active": {
                    "target": "is_active",
                    "transform": "mysql_bool_to_pg",
                    "default": True,
                },
                "created_at": {"target": "created_at"},
                "updated_at": {"target": "updated_at"},
            },
            "custom_mappings": {
                "privilege_id": {"source": "id", "transform": "fedena_id_to_uuid"},
            },
            "tenant_field": True,
            "dependencies": [],
        },
        "privileges_users": {
            "target_model": "core_userprivilege",
            "fields": {
                "user_id": {"target": "user_id", "transform": "fedena_id_to_uuid"},
                "privilege_id": {
                    "target": "privilege_id",
                    "transform": "fedena_id_to_uuid",
                },
                "created_at": {"target": "created_at"},
                "updated_at": {"target": "updated_at"},
            },
            "tenant_field": True,
            "dependencies": ["users", "privileges"],
        },
        # =================================================================
        # LIBRARY MANAGEMENT
        # =================================================================
        "books": {
            "target_model": "core_book",
            "fields": {
                "id": {"target": "id", "transform": "fedena_id_to_uuid"},
                "title": {"target": "title"},
                "author": {"target": "author"},
                "isbn": {"target": "isbn"},
                "subject_id": {
                    "target": "subject_id",
                    "transform": "fedena_id_to_uuid",
                },
                "book_number": {"target": "book_number"},
                "edition": {"target": "edition"},
                "publisher": {"target": "publisher"},
                "price": {"target": "price"},
                "ceded_date": {"target": "acquired_date"},
                "is_deleted": {"target": "is_active", "transform": "invert_mysql_bool"},
                "created_at": {"target": "created_at"},
                "updated_at": {"target": "updated_at"},
            },
            "tenant_field": True,
            "dependencies": ["subjects"],
            # Book.book_number is globally unique.
            "dedupe_key": "book_number",
        },
        # =================================================================
        # COMMUNICATION TABLES
        # =================================================================
        "messages": {
            "target_model": "core_message",
            "fields": {
                "id": {"target": "id", "transform": "fedena_id_to_uuid"},
                "author_id": {"target": "author_id", "transform": "fedena_id_to_uuid"},
                "subject": {"target": "subject", "default": "Migrated Message"},
                "body": {"target": "body"},
                "is_read": {"target": "is_read", "default": False},
                "sent_date": {"target": "sent_date", "default": "created_at"},
                "is_deleted_by_sender": {
                    "target": "is_deleted_by_sender",
                    "transform": "mysql_bool_to_pg",
                },
                "created_at": {"target": "created_at"},
                "updated_at": {"target": "updated_at"},
            },
            "tenant_field": True,
            "dependencies": ["users"],
        },
        "news": {
            "target_model": "core_news",
            "fields": {
                "id": {"target": "id", "transform": "fedena_id_to_uuid"},
                "title": {"target": "title"},
                "content": {"target": "content"},
                "author": {"target": "author"},
                "is_active": {"target": "is_active", "transform": "mysql_bool_to_pg"},
                "created_at": {"target": "created_at"},
                "updated_at": {"target": "updated_at"},
            },
            "tenant_field": True,
            "dependencies": [],
        },
        "notifications": {
            "target_model": "core_notification",
            "fields": {
                "id": {"target": "id", "transform": "fedena_id_to_uuid"},
                "recipient_id": {
                    "target": "recipient_id",
                    "transform": "fedena_id_to_uuid",
                },
                "sender_id": {"target": "sender_id", "transform": "fedena_id_to_uuid"},
                "title": {"target": "title", "default": "Migrated Notification"},
                "message": {"target": "message", "default": "Migrated notification message"},
                "is_read": {"target": "is_read", "transform": "mysql_bool_to_pg"},
                "is_active": {"target": "is_active", "default": True},
                "notification_type": {"target": "notification_type"},
                "created_at": {"target": "created_at"},
                "updated_at": {"target": "updated_at"},
            },
            "tenant_field": True,
            "dependencies": ["users"],
        },
        # =================================================================
        # EVENTS & CALENDAR
        # =================================================================
        "events": {
            "target_model": "core_event",
            "fields": {
                "id": {"target": "id", "transform": "fedena_id_to_uuid"},
                "title": {"target": "title"},
                "description": {"target": "description"},
                "start_date": {"target": "start_date"},
                "end_date": {"target": "end_date"},
                # start_time and end_time don't exist in source table, only start_date/end_date
                "is_common": {"target": "is_common", "transform": "mysql_bool_to_pg"},
                "origin_id": {"target": "origin_id"},  # Keep as integer, don't transform to UUID
                "origin_type": {"target": "origin_type"},
                "is_due": {"target": "is_due", "transform": "mysql_bool_to_pg", "default": False},
                "is_holiday": {"target": "is_holiday", "transform": "mysql_bool_to_pg", "default": False},
                "is_exam": {"target": "is_exam", "transform": "mysql_bool_to_pg", "default": False},
                "created_at": {"target": "created_at"},
                "updated_at": {"target": "updated_at"},
            },
            "default_values": {
                "is_holiday": False,
                "is_exam": False,
                "is_due": False,
                "is_common": False,
            },
            "tenant_field": True,
            "dependencies": [],
        },
        # =================================================================
        # ADMISSION SYSTEM TABLES
        # =================================================================
        # Note: Temporarily skip applicants due to missing required course_applied ForeignKey
        # Will need to fix courses table first, then come back to applicants
        # 'applicants': {
        #     'target_model': 'core_admissionapplication',
        #     'fields': {
        #         'id': {'target': 'id', 'transform': 'fedena_id_to_uuid'},
        #         'reg_no': {'target': 'application_number'},
        #         'first_name': {'target': 'first_name'},
        #         'last_name': {'target': 'last_name'},
        #         'date_of_birth': {'target': 'date_of_birth'},
        #         'gender': {'target': 'gender', 'default': 'other'},
        #         'address_line1': {'target': 'address'},
        #         'guardian_name': {'target': 'guardian_name', 'default': 'Guardian'},
        #         'phone1': {'target': 'guardian_phone'},
        #         'course_applied': {'target': 'course_applied', 'default_lookup': 'first_course'},
        #     },
        #     'dependencies': ['courses']
        # },
        # =================================================================
        # SYSTEM & CONFIGURATION TABLES
        # =================================================================
        "countries": {
            "target_model": "core_country",
            "fields": {
                # Map a deterministic id so re-runs hit ON CONFLICT (id) DO NOTHING
                # instead of minting a fresh UUID and duplicating every country.
                "id": {"target": "id", "transform": "fedena_id_to_uuid"},
                "name": {"target": "name"},
                "code": {"target": "code"},
                "currency_code": {"target": "currency_code"},
                "regional_name": {"target": "regional_name"},
                "created_at": {"target": "created_at"},
                "updated_at": {"target": "updated_at"},
            },
            "tenant_field": False,  # Countries are global
            "dependencies": [],
        },
        "configurations": {
            "target_model": "core_configuration",
            "fields": {
                "id": {"target": "id", "transform": "fedena_id_to_uuid"},
                "config_key": {"target": "config_key"},
                "config_value": {"target": "config_value"},
                # description field doesn't exist in Configuration model - removed
                "created_at": {"target": "created_at"},
                "updated_at": {"target": "updated_at"},
            },
            "tenant_field": True,
            "dependencies": [],
        },
        "schools": {
            "target_model": "core_school",
            "fields": {
                "id": {"target": "id", "transform": "fedena_id_to_uuid"},
                "name": {"target": "name"},
                "code": {"target": "code"},
                "address_line1": {"target": "address_line1"},
                "address_line2": {"target": "address_line2"},
                "city": {"target": "city"},
                "state": {"target": "state"},
                "country_id": {
                    "target": "country_id",
                    "transform": "fedena_id_to_uuid",
                },
                "pin_code": {"target": "pin_code"},
                "phone": {"target": "phone"},
                "email": {"target": "email"},
                "website": {"target": "website"},
                "is_active": {"target": "is_active", "transform": "mysql_bool_to_pg"},
                "created_at": {"target": "created_at"},
                "updated_at": {"target": "updated_at"},
            },
            "tenant_field": False,  # Schools are tenant definitions
            "dependencies": ["countries"],
        },
        # =================================================================
        # EXTENDED ACADEMIC TABLES
        # =================================================================
        "student_additional_details": {
            "target_model": "core_studentadditionaldetail",
            "fields": {
                "id": {"target": "id", "transform": "fedena_id_to_uuid"},
                "student_id": {
                    "target": "student_id",
                    "transform": "fedena_id_to_uuid",
                },
                # NOTE: the source has one row per (student, additional_field), but
                # core_studentadditionaldetail is OneToOne(student) with only an
                # additional_info text column — there is no additional_field_id column.
                # Mapping it would raise "column does not exist". We keep additional_info
                # and dedupe to one row per student (see dedupe_key) so the OneToOne
                # constraint isn't violated. The per-field breakdown can't be preserved
                # in this target model.
                "additional_info": {"target": "additional_info"},
                "created_at": {"target": "created_at"},
                "updated_at": {"target": "updated_at"},
            },
            "tenant_field": True,
            "dependencies": ["students"],
            # OneToOne(student) — only one detail row per student may exist.
            "dedupe_key": "student_id",
        },
        "additional_fields": {
            "target_model": "core_additionalfield",
            "fields": {
                "id": {"target": "id", "transform": "fedena_id_to_uuid"},
                "name": {"target": "name"},
                "is_mandatory": {
                    "target": "is_mandatory",
                    "transform": "mysql_bool_to_pg",
                },
                "input_type": {"target": "input_type"},
                "created_at": {"target": "created_at"},
                "updated_at": {"target": "updated_at"},
            },
            "tenant_field": True,
            "dependencies": [],
        },
        "student_previous_datas": {
            "target_model": "core_studentpreviousdata",
            "fields": {
                "id": {"target": "id", "transform": "fedena_id_to_uuid"},
                "student_id": {
                    "target": "student_id",
                    "transform": "fedena_id_to_uuid",
                },
                "institution": {"target": "institution"},
                "year": {"target": "year"},
                "course": {"target": "course"},
                "total_mark": {"target": "total_mark"},
                # NOTE: source column "mark_obtained" has no field on
                # core_studentpreviousdata (it only has total_mark) — mapping it would
                # raise "column does not exist". Dropped; total_mark is preserved.
                "created_at": {"target": "created_at"},
                "updated_at": {"target": "updated_at"},
            },
            "tenant_field": True,
            "dependencies": ["students"],
        },
        "archived_students": {
            "target_model": "core_archivedstudent",
            "fields": {
                "id": {"target": "id", "transform": "fedena_id_to_uuid"},
                "former_id": {"target": "former_id"},
                "first_name": {"target": "first_name"},
                "middle_name": {"target": "middle_name"},
                "last_name": {"target": "last_name"},
                "admission_no": {"target": "admission_no"},
                # batch_name field doesn't exist in source, will use default value
                # date_of_birth field doesn't exist in ArchivedStudent model - removed
                "status_description": {"target": "status_description"},
                "created_at": {"target": "created_at"},
                "updated_at": {"target": "updated_at"},
            },
            "tenant_field": True,
            "dependencies": [],
            "default_values": {
                "batch_name": "Migrated Batch",  # Required field with default (source table has batch_id not batch_name)
                "course_name": "Unknown Course",  # Required field with default
                "date_of_leaving": "2023-01-01",  # Required field with default
            },
        },
        # =================================================================
        # SUBJECT & SKILLS MANAGEMENT
        # =================================================================
        # Step 1: migrate skill set categories (Fedena: subject_skill_sets → Pinewood: core_skillset)
        "subject_skill_sets": {
            "target_model": "core_skillset",
            "fields": {
                "id": {"target": "id", "transform": "fedena_id_to_uuid"},
                "name": {"target": "name"},
                # code is derived from name in transform_record post-processing (see core_skillset block)
                "created_at": {"target": "created_at"},
                "updated_at": {"target": "updated_at"},
            },
            "tenant_field": True,
            "dependencies": [],
            "default_values": {
                "is_active": True,
            },
        },
        # Step 2: migrate individual skills (Fedena: subject_skills → Pinewood: core_skill)
        "subject_skills": {
            "target_model": "core_skill",
            "fields": {
                "id": {"target": "id", "transform": "fedena_id_to_uuid"},
                "name": {"target": "name"},
                # Map the FK from Fedena skill set to Pinewood skill_set_id
                "subject_skill_set_id": {
                    "target": "skill_set_id",
                    "transform": "fedena_id_to_uuid",
                },
                "created_at": {"target": "created_at"},
                "updated_at": {"target": "updated_at"},
            },
            "tenant_field": True,
            "dependencies": ["subject_skill_sets"],
            "default_values": {
                "order": 0,
                "is_active": True,
            },
        },
        # Note: skill_assessments mapping removed - use existing SkillsAssessment system instead
        # =================================================================
        # REPORTS & ANALYTICS
        # =================================================================
        "reports": {
            "target_model": "core_report",
            "fields": {
                "id": {"target": "id", "transform": "fedena_id_to_uuid"},
                "name": {"target": "name"},
                "description": {"target": "description"},
                "report_type": {"target": "report_type", "default": "CUSTOM"},
                "is_active": {"target": "is_active", "transform": "mysql_bool_to_pg"},
                "created_at": {"target": "created_at"},
                "updated_at": {"target": "updated_at"},
            },
            "tenant_field": True,
            "dependencies": [],
        },
        "generated_reports": {
            "target_model": "core_generatedreport",
            "fields": {
                "id": {"target": "id", "transform": "fedena_id_to_uuid"},
                "report_id": {"target": "report_id", "transform": "fedena_id_to_uuid"},
                "generated_by": {
                    "target": "generated_by",
                    "transform": "fedena_id_to_uuid",
                },
                "file_name": {"target": "file_name"},
                "file_path": {"target": "file_path"},
                "status": {"target": "status"},
                "created_at": {"target": "created_at"},
                "updated_at": {"target": "updated_at"},
            },
            "tenant_field": True,
            "dependencies": ["reports", "users"],
        },
        # =================================================================
        # REMAINING HIGH-VALUE TABLES
        # =================================================================
        "sms_messages": {
            "target_model": "core_sms",
            "fields": {
                "id": {"target": "id", "transform": "fedena_id_to_uuid"},
                "recipient": {"target": "recipient"},
                "message": {"target": "body", "default": "Migrated SMS message"},
                "sent_date": {"target": "sent_date"},
                "status": {"target": "status"},
                "created_at": {"target": "created_at"},
                "updated_at": {"target": "updated_at"},
            },
            "tenant_field": True,
            "dependencies": [],
            "filters": ['message IS NOT NULL AND message != ""'],
        },
        "financial_years": {
            "target_model": "core_financialyear",
            "fields": {
                "id": {"target": "id", "transform": "fedena_id_to_uuid"},
                "name": {"target": "name"},
                "start_date": {"target": "start_date"},
                "end_date": {"target": "end_date"},
                "is_active": {"target": "is_active", "transform": "mysql_bool_to_pg"},
                "created_at": {"target": "created_at"},
                "updated_at": {"target": "updated_at"},
            },
            "tenant_field": True,
            "dependencies": [],
        },
        "weekday_sets_weekdays": {
            "target_model": "core_weekdaysetweekday",
            "fields": {
                "id": {"target": "id", "transform": "fedena_id_to_uuid"},
                "weekday_set_id": {
                    "target": "weekday_set_id",
                    "transform": "fedena_id_to_uuid",
                },
                "weekday_id": {
                    "target": "weekday_id",
                    "transform": "fedena_id_to_uuid",
                },
                "created_at": {"target": "created_at"},
                "updated_at": {"target": "updated_at"},
            },
            "tenant_field": True,
            "dependencies": ["weekday_sets"],
        },
        # Additional high-value tables that should be mapped
        "time_zones": {
            "target_model": "core_timezone",
            "fields": {
                "id": {"target": "id", "transform": "fedena_id_to_uuid"},
                "name": {"target": "name"},
                "zone": {"target": "zone"},
                "created_at": {"target": "created_at"},
                "updated_at": {"target": "updated_at"},
            },
            "tenant_field": True,  # Timezones need tenant_id in target schema
            "dependencies": [],
        },
        # =================================================================
        # CRITICAL MISSING TABLES
        # =================================================================
        "admin_users": {
            "target_model": "core_user",
            "fields": {
                "id": {"target": "id", "transform": "fedena_id_to_uuid"},
                "username": {"target": "username"},
                "email": {"target": "email"},
                "full_name": {"target": "first_name"},  # Map to first_name field
                "crypted_password": {"target": "password"},
                "type": {
                    "target": "is_admin",
                    "transform": "admin_type_to_bool",
                },  # Map to is_admin flag
                "created_at": {"target": "created_at"},
                "updated_at": {"target": "updated_at"},
            },
            "tenant_field": False,  # UserProfile handles tenant relationship differently
            "dependencies": [],
            "default_values": {
                "last_name": "User",  # Default last name
                "is_verified": True,  # Admin users are verified by default
            },
        },
        "fee_discounts": {
            "target_model": "core_feediscount",
            "fields": {
                "id": {"target": "id", "transform": "fedena_id_to_uuid"},
                "name": {"target": "name"},
                "type": {"target": "discount_type", "transform": "null_to_batch_discount_type"},
                "finance_fee_category_id": {
                    "target": "fee_category_id",
                    "transform": "fedena_id_to_uuid",
                },
                "discount": {"target": "discount_value"},
                "is_amount": {"target": "discount_mode", "transform": "is_amount_to_mode"},
                "created_at": {"target": "created_at"},
                "updated_at": {"target": "updated_at"},
            },
            "tenant_field": True,
            "dependencies": ["finance_fee_categories"],
            "filters": [
                "finance_fee_category_id IN (SELECT id FROM finance_fee_categories WHERE is_deleted = 0 OR is_deleted IS NULL)",
            ],
            "default_values": {
                "is_active": True,
                "discount_type": "batch",  # Default to batch discount type since Fedena type field is null
            },
        },
        "fee_invoices": {
            "target_model": "core_feeinvoice",
            "fields": {
                "id": {"target": "id", "transform": "fedena_id_to_uuid"},
                "invoice_number": {"target": "invoice_number"},
                "created_at": {"target": "created_at"},
                "updated_at": {"target": "updated_at"},
            },
            "custom_mappings": {
                "student_id": {"source": "fee_id", "transform": "fee_id_to_student_uuid"},
                "fee_category_id": {"source": "fee_id", "transform": "fee_id_to_fee_category_uuid"},
            },
            "tenant_field": True,
            "dependencies": ["students", "finance_fee_categories", "academic_years", "finance_fees"],
            "default_values": {
                "total_amount": 0.0,
                "paid_amount": 0.0,
                "balance_amount": 0.0,
                "due_date": "2024-12-31",
                "invoice_date": "2024-01-01",
                "status": "DRAFT",
                "is_active": True,
                # academic_year_id resolved dynamically via fix_missing_foreign_keys_universal
            },
            "filters": [
                "fee_id IN (SELECT id FROM finance_fees WHERE student_id IN (SELECT id FROM students WHERE is_deleted = 0 OR is_deleted IS NULL))",
                "fee_id IS NOT NULL",
            ],
        },
        "fine_rules": {
            "target_model": "core_finerule",
            "fields": {
                "id": {"target": "id", "transform": "fedena_id_to_uuid"},
                "fine_days": {"target": "fine_days"},
                "is_amount": {"target": "is_amount", "transform": "mysql_bool_to_pg"},
                "fine_amount": {"target": "fine_amount"},
                "fee_category_id": {
                    "target": "fee_category_id",
                    "transform": "fedena_id_to_uuid",
                },
                "created_at": {"target": "created_at"},
                "updated_at": {"target": "updated_at"},
                "is_active": {"target": "is_active", "default": True},
            },
            "tenant_field": True,
            "dependencies": ["finance_fee_categories"],
        },
        "fines": {
            "target_model": "core_fine",
            "fields": {
                "id": {"target": "id", "transform": "fedena_id_to_uuid"},
                "student_id": {
                    "target": "student_id",
                    "transform": "fedena_id_to_uuid",
                },
                "fine_amount": {"target": "fine_amount", "default": 0.0},
                "fine_date": {"target": "fine_date", "default": "2024-01-01"},
                "is_paid": {"target": "is_paid", "transform": "mysql_bool_to_pg", "default": False},
                "created_at": {"target": "created_at"},
                "updated_at": {"target": "updated_at"},
            },
            "tenant_field": True,
            "dependencies": ["students", "fine_rules"],
            "filters": [
                "student_id IN (SELECT id FROM students WHERE is_deleted = 0 OR is_deleted IS NULL)",
                "student_id IS NOT NULL",
            ],
            "default_values": {
                # fine_rule_id intentionally not defaulted — records without a valid fine rule are skipped
            },
        },
        "assessment_groups": {
            "target_model": "core_assessmentgroup",
            "fields": {
                "id": {"target": "id", "transform": "fedena_id_to_uuid"},
                "name": {"target": "name"},
                "batch_id": {"target": "batch_id", "transform": "fedena_id_to_uuid"},
                "exam_type": {"target": "exam_type"},
                "is_published": {
                    "target": "is_published",
                    "transform": "mysql_bool_to_pg",
                },
                "created_at": {"target": "created_at"},
                "updated_at": {"target": "updated_at"},
            },
            "tenant_field": True,
            "dependencies": ["batches"],
        },
        "batch_events": {
            "target_model": "core_batchevent",
            "fields": {
                "id": {"target": "id", "transform": "fedena_id_to_uuid"},
                "batch_id": {"target": "batch_id", "transform": "fedena_id_to_uuid"},
                "event_id": {"target": "event_id", "transform": "fedena_id_to_uuid"},
                "created_at": {"target": "created_at"},
                "updated_at": {"target": "updated_at"},
            },
            "tenant_field": True,
            "dependencies": ["batches", "events"],
        },
        "employee_additional_details": {
            "target_model": "core_employeeadditionaldetail",
            "fields": {
                "id": {"target": "id", "transform": "fedena_id_to_uuid"},
                "employee_id": {
                    "target": "employee_id",
                    "transform": "fedena_id_to_uuid",
                },
                "additional_field_id": {
                    "target": "additional_field_id",
                    "transform": "fedena_id_to_uuid",
                },
                "additional_info": {"target": "additional_info"},
                "created_at": {"target": "created_at"},
                "updated_at": {"target": "updated_at"},
            },
            "tenant_field": True,
            "dependencies": ["employees", "additional_fields"],
        },
        # Critical unmapped tables with significant data
        "individual_reports": {
            "target_model": "core_individualreport",
            "fields": {
                "id": {"target": "id", "transform": "fedena_id_to_uuid"},
                "reportable_id": {
                    "target": "reportable_id",
                    "transform": "fedena_id_to_uuid",
                },
                "reportable_type": {"target": "reportable_type"},
                "student_id": {
                    "target": "student_id",
                    "transform": "fedena_id_to_uuid",
                },
                "generated_report_batch_id": {
                    "target": "generated_report_batch_id",
                    "transform": "fedena_id_to_uuid",
                },
                "report": {"target": "report"},
                "report_component": {"target": "report_component"},
                "created_at": {"target": "created_at"},
                "updated_at": {"target": "updated_at"},
            },
            "tenant_field": True,
            "dependencies": ["students", "generated_reports"],
        },
        "converted_assessment_marks": {
            "target_model": "core_convertedassessmentmark",
            "fields": {
                "id": {"target": "id", "transform": "fedena_id_to_uuid"},
                "markable_id": {
                    "target": "markable_id",
                    "transform": "fedena_id_to_uuid",
                },
                "markable_type": {"target": "markable_type"},
                "assessment_group_batch_id": {
                    "target": "assessment_group_batch_id",
                    "transform": "fedena_id_to_uuid",
                },
                "assessment_group_id": {
                    "target": "assessment_group_id",
                    "transform": "fedena_id_to_uuid",
                },
                "student_id": {
                    "target": "student_id",
                    "transform": "fedena_id_to_uuid",
                },
                "mark": {"target": "mark"},
                "grade": {"target": "grade"},
                "grade_points": {"target": "grade_points"},
                "passed": {"target": "passed", "transform": "mysql_bool_to_pg"},
                "description": {"target": "description"},
                "is_absent": {"target": "is_absent", "transform": "mysql_bool_to_pg"},
                "actual_mark": {"target": "actual_mark"},
                "created_at": {"target": "created_at"},
                "updated_at": {"target": "updated_at"},
            },
            "tenant_field": True,
            "dependencies": ["students", "assessment_groups"],
        },
        "finance_transaction_receipt_records": {
            "target_model": "core_financetransactionreceiptrecord",
            "fields": {
                "id": {"target": "id", "transform": "fedena_id_to_uuid"},
                "finance_transaction_id": {
                    "target": "finance_transaction_id",
                    "transform": "fedena_id_to_uuid",
                },
                "transaction_receipt_id": {
                    "target": "transaction_receipt_id",
                    "transform": "fedena_id_to_uuid",
                },
                "fee_account_id": {
                    "target": "fee_account_id",
                    "transform": "fedena_id_to_uuid",
                },
                "fee_receipt_template_id": {
                    "target": "fee_receipt_template_id",
                    "transform": "fedena_id_to_uuid",
                },
                "precision_count": {"target": "precision_count"},
                "receipt_data": {"target": "receipt_data"},
                "created_at": {"target": "created_at"},
                "updated_at": {"target": "updated_at"},
            },
            "tenant_field": True,
            "dependencies": ["finance_transactions"],
        },
        "finance_transaction_ledgers": {
            "target_model": "core_financetransactionledger",
            "fields": {
                "id": {"target": "id", "transform": "fedena_id_to_uuid"},
                "id_for_transaction": {"target": "finance_transaction_id", "transform": "ledger_id_to_finance_transaction_id", "source_field": "id"},
                "fee_account_id": {
                    "target": "fee_account_id",
                    "transform": "fedena_id_to_uuid",
                },
                "amount": {"target": "amount"},
                "created_at": {"target": "created_at"},
                "updated_at": {"target": "updated_at"},
            },
            "tenant_field": True,
            "dependencies": ["finance_transactions"],
        },
        "notification_recipients": {
            "target_model": "core_notificationrecipient",
            "fields": {
                "id": {"target": "id", "transform": "fedena_id_to_uuid"},
                "notification_id": {
                    "target": "notification_id",
                    "transform": "fedena_id_to_uuid",
                },
                "recipient_id": {
                    "target": "recipient_id",
                    "transform": "fedena_id_to_uuid",
                },
                "recipient_type": {"target": "recipient_type"},
                "is_read": {"target": "is_read", "transform": "mysql_bool_to_pg"},
                "created_at": {"target": "created_at"},
                "updated_at": {"target": "updated_at"},
            },
            "tenant_field": True,
            "dependencies": ["notifications"],
        },
        "sms_logs": {
            "target_model": "core_smslog",
            "fields": {
                "id": {"target": "id", "transform": "fedena_id_to_uuid"},
                "mobile_number": {"target": "mobile_number"},
                "message": {"target": "message"},
                "status": {"target": "status"},
                "sent_at": {"target": "sent_at"},
                "created_at": {"target": "created_at"},
                "updated_at": {"target": "updated_at"},
            },
            "tenant_field": True,
            "dependencies": [],
            "filters": [
                'mobile_number IS NOT NULL AND mobile_number != "" AND mobile_number != "NULL"'
            ],
        },
    }

    # Foundation-first tie-breaker for the topological sort. Hard dependencies (the
    # "dependencies" list above) always gate ordering; this priority only decides which
    # of the currently-ready tables to emit first. Lower number = earlier. It ensures
    # global/system and reference tables land before the entities that fall back to them
    # (e.g. get_first_country_id / get_first_course_id). Tables not listed default to 5.
    TABLE_PRIORITY = {
        # tier 0 — global / system tables
        "countries": 0, "time_zones": 0, "schools": 0, "configurations": 0,
        # tier 1 — tenant reference / lookup tables (independent, widely referenced)
        "academic_years": 1, "financial_years": 1, "student_categories": 1,
        "employee_categories": 1, "employee_departments": 1, "employee_positions": 1,
        "employee_grades": 1, "additional_fields": 1, "attendance_labels": 1,
        "weekday_sets": 1, "class_timings": 1, "grades": 1,
        "finance_fee_categories": 1, "finance_transaction_categories": 1,
        "subject_skill_sets": 1, "privileges": 1,
        # tier 2 — primary entities everything else hangs off of
        "users": 2, "admin_users": 2, "courses": 2, "employees": 2,
        "students": 2, "guardians": 2,
    }


class FedenaDataTransformer:
    """Transforms Fedena data to Pinewood format with proper mappings."""

    def __init__(self, sql_file: Optional[str], db_config: Dict[str, str], tenant_id: str, mysql_config: Optional[Dict[str, str]] = None, dry_run: bool = False, max_error_rate: float = 0.05):
        self.sql_file = Path(sql_file) if sql_file else None
        self.db_config = db_config
        self.mysql_config = mysql_config
        self.tenant_id = tenant_id
        self.dry_run = dry_run
        self.max_error_rate = max_error_rate
        self.connection = None
        self.mysql_connection = None

        # Cache for SQL file contents — loaded once, reused per table
        self._sql_cache: Optional[str] = None

        # Track ID mappings for foreign key relationships
        self.id_mappings = {}

        # Per-run caches for "first available" FK fallbacks and lookup transforms.
        # These values don't change mid-run, so memoizing them removes thousands of
        # redundant per-record SELECTs.
        self._first_id_cache: Dict[str, Optional[str]] = {}
        self._lookup_cache: Dict[str, Dict[Any, Any]] = {}
        # target table -> set of real column names (from information_schema), so we can
        # drop mapped columns that don't exist on the model instead of aborting the
        # whole table's insert. Loaded lazily, once per table.
        self._table_columns_cache: Dict[str, set] = {}
        self._dedupe_id_mappings = {} 

        # Track transformation statistics
        self.stats = {
            'tables_processed': 0,
            'records_transformed': 0,
            'errors': [],
            # Natural-key collisions (same admission_no/code/etc. as an existing row).
            # Kept separate from generic errors so they're visible, not buried.
            'duplicates': [],
        }

    def connect_to_database(self) -> bool:
        """Establish connection to PostgreSQL database."""
        try:
            self.connection = psycopg2.connect(
                host=self.db_config['host'],
                port=self.db_config['port'],
                database=self.db_config['database'],
                user=self.db_config['user'],
                password=self.db_config['password']
            )
            # autocommit=False so each table runs inside an explicit transaction
            self.connection.autocommit = False
            print(f"✓ Connected to PostgreSQL database: {self.db_config['database']}")
            return True
        except Exception as e:
            print(f"✗ Failed to connect to database: {e}")
            return False

    def connect_to_mysql(self) -> bool:
        """Establish connection to MySQL/MariaDB database."""
        if not self.mysql_config:
            print("✗ No MySQL configuration provided")
            return False
        try:
            self.mysql_connection = mysql.connector.connect(
                host=self.mysql_config['host'],
                port=self.mysql_config.get('port', 3306),
                database=self.mysql_config['database'],
                user=self.mysql_config['user'],
                password=self.mysql_config['password'],
                charset='utf8mb4',
                use_unicode=True,
            )
            print(f"✓ Connected to MySQL database: {self.mysql_config['database']}")
            return True
        except Exception as e:
            print(f"✗ Failed to connect to MySQL database: {e}")
            return False

    def parse_fedena_table_data(self, table_name: str) -> List[Dict[str, Any]]:
        """Parse data from specific Fedena table in SQL dump."""
        if not self.sql_file.exists():
            raise FileNotFoundError(f"SQL file not found: {self.sql_file}")

        if self._sql_cache is None:
            print(f"📖 Loading SQL dump into memory (once): {self.sql_file}")
            with open(self.sql_file, 'r', encoding='utf-8') as f:
                self._sql_cache = f.read()
        content = self._sql_cache

        # First get the table structure to know column names
        table_columns = self._get_table_columns(table_name, content)
        if not table_columns:
            return []

        # Find INSERT statements for the specific table
        # Handle both formats: INSERT INTO table (columns) VALUES and INSERT INTO table VALUES
        pattern1 = rf"INSERT INTO `{table_name}`\s*\((.*?)\)\s*VALUES\s*(.*?)(?=;\s*(?:/*!|UNLOCK|INSERT|$))"
        pattern2 = rf"INSERT INTO `{table_name}`\s*VALUES\s*(.*?)(?=;\s*(?:/*!|UNLOCK|INSERT|$))"

        records = []

        # Try pattern with column specification first
        matches = re.finditer(pattern1, content, re.DOTALL | re.IGNORECASE)
        for match in matches:
            columns = [col.strip('`').strip() for col in match.group(1).split(',')]
            values_text = match.group(2)
            values_list = self._parse_values(values_text)

            for values in values_list:
                if len(values) == len(columns):
                    record = dict(zip(columns, values))
                    records.append(record)

        # If no matches, try pattern without column specification
        if not records:
            matches = re.finditer(pattern2, content, re.DOTALL | re.IGNORECASE)
            for match in matches:
                values_text = match.group(1)
                values_list = self._parse_values(values_text)

                for values in values_list:
                    if len(values) == len(table_columns):
                        record = dict(zip(table_columns, values))
                        records.append(record)
                    else:
                        # Pad with None if fewer values than columns
                        while len(values) < len(table_columns):
                            values.append(None)
                        record = dict(zip(table_columns, values[:len(table_columns)]))
                        records.append(record)

        return records

    def fetch_mysql_table_data(self, table_name: str, filters: List[str] = None) -> List[Dict[str, Any]]:
        """Fetch data directly from MySQL database with optional filters."""
        if not self.mysql_connection:
            print("✗ No MySQL connection available")
            return []

        try:
            cursor = self.mysql_connection.cursor(dictionary=True)

            # Build query with filters
            query = f"SELECT * FROM `{table_name}`"
            if filters:
                where_conditions = []
                for filter_condition in filters:
                    where_conditions.append(f"({filter_condition})")
                if where_conditions:
                    query += " WHERE " + " AND ".join(where_conditions)

            cursor.execute(query)
            records = cursor.fetchall()
            cursor.close()

            # Convert any datetime objects to strings for JSON serialization
            for record in records:
                for key, value in record.items():
                    if isinstance(value, (datetime, date)):
                        record[key] = value.isoformat()
                    elif value is None:
                        record[key] = None
                    elif isinstance(value, bytes):
                        # Convert bytes to string (for binary data)
                        try:
                            record[key] = value.decode('utf-8')
                        except:
                            record[key] = str(value)

            return records
        except Exception as e:
            print(f"✗ Error fetching data from MySQL table {table_name}: {e}")
            return []

    def _get_table_columns(self, table_name: str, content: str) -> List[str]:
        """Extract column names from CREATE TABLE statement.

        KEY/INDEX definitions list column names in parentheses after the index
        name, e.g.  KEY `idx` (`col_a`,`col_b`,`col_c`).  Splitting the whole
        table body by comma produces bare `col_b` and `col_c` tokens that look
        exactly like column definitions but aren't.  We use a line-by-line scan
        instead: a real column definition always follows the pattern
            `col_name`  <DATA_TYPE>  ...
        whereas index column references never have a data type after them.
        """
        pattern = rf"CREATE TABLE `{table_name}`\s*\((.*?)\)\s*ENGINE"
        match = re.search(pattern, content, re.DOTALL | re.IGNORECASE)

        if not match:
            return []

        table_def = match.group(1)
        columns = []

        # SQL data type keywords that follow a column name in a column definition.
        # Index references never have these immediately after the backtick-quoted name.
        DATA_TYPES = (
            'int', 'tinyint', 'smallint', 'mediumint', 'bigint',
            'float', 'double', 'decimal', 'numeric', 'real',
            'char', 'varchar', 'tinytext', 'text', 'mediumtext', 'longtext',
            'binary', 'varbinary', 'tinyblob', 'blob', 'mediumblob', 'longblob',
            'date', 'time', 'datetime', 'timestamp', 'year',
            'boolean', 'bool', 'json', 'enum', 'set',
        )

        for line in table_def.splitlines():
            line = line.strip().rstrip(',')
            if not line:
                continue
            upper = line.upper()
            # Skip constraint / index lines
            if upper.startswith(('PRIMARY KEY', 'KEY ', 'INDEX ', 'UNIQUE ', 'CONSTRAINT ', 'FULLTEXT')):
                continue
            # Must start with a backtick-quoted column name
            col_match = re.match(r'`([^`]+)`\s+(\w+)', line)
            if not col_match:
                continue
            # The token after the column name must be a recognised data type
            if col_match.group(2).lower() in DATA_TYPES:
                columns.append(col_match.group(1))

        return columns

    def _parse_values(self, values_text: str) -> List[List]:
        """Parse VALUES clause from INSERT statement."""
        values_list = []

        # Clean up the values text and split by ),( pattern
        values_text = values_text.strip()
        value_sets = re.split(r'\),\s*\(', values_text)

        for i, value_set in enumerate(value_sets):
            # Clean up parentheses from first and last items
            if i == 0:
                value_set = value_set.lstrip('(')
            if i == len(value_sets) - 1:
                value_set = value_set.rstrip(');').rstrip(')')
                # Remove any trailing MySQL comments
                value_set = re.sub(r'\s*;\s*/\*.*$', '', value_set, flags=re.DOTALL)

            values = []
            current_value = ""
            in_quotes = False
            quote_char = None

            i = 0
            while i < len(value_set):
                char = value_set[i]

                if char == '\\' and in_quotes:
                    # MySQL backslash escape inside a quoted string (e.g. \' \" \\).
                    # Keep the two-character sequence intact so the escaped quote is
                    # not mistaken for a string terminator (which would shift every
                    # following column). _clean_value unescapes it afterwards.
                    current_value += char
                    if i + 1 < len(value_set):
                        current_value += value_set[i + 1]
                        i += 2
                    else:
                        i += 1
                    continue

                if char in ("'", '"') and not in_quotes:
                    in_quotes = True
                    quote_char = char
                elif char == quote_char and in_quotes:
                    if i + 1 < len(value_set) and value_set[i + 1] == quote_char:
                        current_value += char
                        i += 1
                    else:
                        in_quotes = False
                        quote_char = None
                elif char == ',' and not in_quotes:
                    values.append(self._clean_value(current_value.strip()))
                    current_value = ""
                    i += 1
                    continue

                current_value += char
                i += 1

            if current_value.strip():
                values.append(self._clean_value(current_value.strip()))

            if values:  # Only add non-empty value sets
                values_list.append(values)

        return values_list

    # MySQL string-literal backslash escapes (default sql_mode, NO_BACKSLASH_ESCAPES off).
    _MYSQL_ESCAPES = {
        '0': '\0', 'b': '\b', 'n': '\n', 'r': '\r', 't': '\t',
        'Z': '\x1a', '\\': '\\', "'": "'", '"': '"',
        # \% and \_ keep the backslash outside LIKE context.
        '%': '\\%', '_': '\\_',
    }

    def _unescape_mysql_string(self, s: str) -> str:
        """Unescape a MySQL single/double-quoted string body in one left-to-right
        pass, so an escaped backslash (\\\\) preceding a quote is handled correctly."""
        out = []
        i = 0
        n = len(s)
        while i < n:
            c = s[i]
            if c == '\\' and i + 1 < n:
                nxt = s[i + 1]
                out.append(self._MYSQL_ESCAPES.get(nxt, nxt))
                i += 2
            else:
                out.append(c)
                i += 1
        return ''.join(out)

    def _clean_value(self, value: str) -> Optional[Any]:
        """Clean and convert MySQL values."""
        value = value.strip()

        if value.upper() == 'NULL':
            return None

        if value.startswith(("'", '"')) and value.endswith(("'", '"')):
            return self._unescape_mysql_string(value[1:-1])

        # Handle boolean values
        if value in ('0', 'false', 'FALSE'):
            return False
        elif value in ('1', 'true', 'TRUE'):
            return True

        # Try to convert to appropriate type
        try:
            if '.' in value:
                return float(value)
            else:
                return int(value)
        except ValueError:
            return value

    def generate_uuid_for_fedena_id(self, fedena_id: int, table_name: str) -> str:
        """Generate consistent UUID for Fedena ID."""
        original_table = {
            "academic_years": "academic_years",
            "courses": "courses",
            "batches": "batches",
            "students": "students",
            "employees": "employees",
        }.get(table_name, table_name)

        key = f"{original_table}:{fedena_id}"

        if key not in self.id_mappings:
            # Generate deterministic UUID based on original table and ID
            self.id_mappings[key] = self.deterministic_id(key)

        return self.id_mappings[key]

    # Shared namespace for all deterministic UUIDs so the same logical key always
    # maps to the same UUID across runs — this is what makes re-running idempotent.
    _UUID_NAMESPACE = uuid.UUID("6ba7b810-9dad-11d1-80b4-00c04fd430c8")

    def deterministic_id(self, *parts: Any) -> str:
        """Deterministic UUID from arbitrary key parts.

        Used for records that have no single Fedena integer id (junction tables,
        derived relations). Given the same parts, always returns the same UUID, so
        ON CONFLICT (id) DO NOTHING makes re-runs idempotent instead of duplicating.
        """
        key = ":".join("" if p is None else str(p) for p in parts)
        return str(uuid.uuid5(self._UUID_NAMESPACE, key))


    def transform_field_value(
        self, value: Any, transform_type: str, source_table: str = None
    ) -> Any:
        """Transform field value based on transformation type."""
        # Special handling for transformations that need to process None values
        if value is None and transform_type not in ["null_to_batch_discount_type", "null_to_zero"]:
            return None

        if transform_type == "fedena_id_to_uuid":
            if isinstance(value, (int, str)):
                try:
                    uuid_value = self.generate_uuid_for_fedena_id(int(value), source_table)
                    return uuid_value
                except ValueError:
                    return None
            return None

        elif transform_type == "mysql_bool_to_pg":
            if isinstance(value, int):
                return bool(value)
            if isinstance(value, str):
                return value.lower() in ("1", "true", "yes")
            return bool(value)

        elif transform_type == "invert_mysql_bool":
            if isinstance(value, int):
                return not bool(value)
            if isinstance(value, str):
                return not (value.lower() in ("1", "true", "yes"))
            return not bool(value)

        elif transform_type == "gender_to_bool":
            if isinstance(value, str):
                return value.lower() == "m"  # True for male, False for female
            return bool(value)

        elif transform_type == "gender_to_full":
            if isinstance(value, str):
                gender_map = {
                    "m": "male",
                    "f": "female",
                    "male": "male",
                    "female": "female",
                    "other": "other"
                }
                return gender_map.get(value.lower(), "other")
            return "other"

        elif transform_type == "first_name_as_last_name":
            return value

        elif transform_type == "admin_type_to_bool":
            if isinstance(value, str):
                return value in ("MultiSchoolAdmin", "Admin", "admin")  # True for admin types
            return bool(value)

        elif transform_type == "attendance_type_to_bool":
            if isinstance(value, str):
                return value.lower() in ("present", "late")  # True for present/late, False for absent
            return bool(value)

        elif transform_type == "is_amount_to_mode":
            # Convert Fedena is_amount boolean to Pinewood discount_mode
            if isinstance(value, int):
                return "amount" if value else "percentage"
            if isinstance(value, str):
                return "amount" if value.lower() in ("1", "true", "yes") else "percentage"
            return "amount" if bool(value) else "percentage"
        elif transform_type == "null_to_batch_discount_type":
            # Convert NULL discount type to "batch" default
            if value is None or value == "NULL" or value == "":
                return "batch"
            return value
        elif transform_type == "null_to_zero":
            # Convert NULL numeric values to 0.0
            if value is None or value == "NULL":
                return 0.0
            return value
        elif transform_type == "to_int":
            # Cast value to integer (handles booleans, floats, strings)
            try:
                return int(value)
            except (TypeError, ValueError):
                return 0
        elif transform_type == "grade_name_to_code":
            # Convert grade name to unique code (uppercase, replace spaces with underscores)
            if value is None or value == "":
                return "GRADE"
            # Clean up the name and make it a valid code
            code = str(value).upper().replace(" ", "_").replace("-", "_")
            # Remove any non-alphanumeric characters except underscores
            import re
            code = re.sub(r'[^A-Z0-9_]', '', code)
            # Ensure it's not empty and has reasonable length
            if not code:
                return "GRADE"
            return code[:20]  # Limit to 20 characters
        elif transform_type == "grade_name_id_to_unique_code":
            # Convert grade name + ID to unique code to handle duplicates
            if value is None or value == "":
                # Generate code from source table and record context if available
                return f"GRADE_{source_table if source_table else 'UNKNOWN'}"
            # Clean up the name and make it a valid code
            code = str(value).upper().replace(" ", "_").replace("-", "_")
            # Remove any non-alphanumeric characters except underscores
            import re
            code = re.sub(r'[^A-Z0-9_]', '', code)
            # Ensure it's not empty
            if not code:
                code = "GRADE"
            return code[:15]  # Limit to 15 characters to leave room for ID suffix

        elif transform_type == "fee_collection_to_category_id":
            # Transform fee_collection_id to fee_category_id via fee_collections lookup
            if value is None:
                return None

            cache = self._lookup_cache.setdefault("fee_collection_to_category_id", {})
            if value in cache:
                return cache[value]

            resolved = None
            try:
                if self.mysql_connection:
                    # Live MySQL mode: query source directly
                    cursor = self.mysql_connection.cursor()
                    cursor.execute(
                        "SELECT fee_category_id FROM finance_fee_collections WHERE id = %s",
                        (value,)
                    )
                    result = cursor.fetchone()
                    cursor.close()
                    if result:
                        resolved = self.generate_uuid_for_fedena_id(result[0], "finance_fee_categories")
                else:
                    # Dump-file mode: fee_collections are already in PG as core_feecollection
                    fee_coll_uuid = self.generate_uuid_for_fedena_id(int(value), "finance_fee_collections")
                    cursor = self.connection.cursor()
                    cursor.execute(
                        'SELECT "fee_category_id" FROM "core_feecollection" WHERE id = %s',
                        (fee_coll_uuid,)
                    )
                    result = cursor.fetchone()
                    cursor.close()
                    if result:
                        resolved = str(result[0])  # already a UUID in PG
                if resolved is None:
                    print(f"   ⚠️  Fee collection {value} not found, skipping record")
            except Exception as e:
                print(f"   ⚠️  Error looking up fee collection {value}: {e}")
                return None

            cache[value] = resolved
            return resolved

        elif transform_type == "ledger_id_to_finance_transaction_id":
            # Transform ledger ID to corresponding finance_transaction_id
            if value is None:
                return None
            try:
                # Find the finance_transaction that references this ledger
                cursor = self.mysql_connection.cursor()
                cursor.execute(
                    "SELECT id FROM finance_transactions WHERE transaction_ledger_id = %s",
                    (value,)
                )
                result = cursor.fetchone()
                cursor.close()
                if result:
                    finance_transaction_id = result[0]
                    # Transform the finance_transaction_id to UUID
                    return self.generate_uuid_for_fedena_id(finance_transaction_id, "finance_transactions")
                else:
                    print(f"   ⚠️  Finance transaction for ledger {value} not found, skipping record")
                    return None
            except Exception as e:
                print(f"   ⚠️  Error looking up finance transaction for ledger {value}: {e}, skipping record")
                return None

        elif transform_type == "fee_id_to_student_uuid":
            # Transform finance_fee id to student_id via finance_fees lookup
            if value is None:
                return None

            try:
                cursor = self.mysql_connection.cursor()
                cursor.execute(
                    "SELECT student_id FROM finance_fees WHERE id = %s",
                    (value,)
                )
                result = cursor.fetchone()
                cursor.close()
                if result:
                    student_id = result[0]
                    # Convert to UUID using the student mapping
                    return self.generate_uuid_for_fedena_id(student_id, "students")
                else:
                    print(f"   ⚠️  Finance fee {value} not found, skipping record")
                    return None
            except Exception as e:
                print(f"   ⚠️  Error looking up finance fee {value}: {e}, skipping record")
                return None

        elif transform_type == "fee_id_to_fee_category_uuid":
            # Transform finance_fee id to fee_category_id via finance_fees lookup
            if value is None:
                return None

            try:
                cursor = self.mysql_connection.cursor()
                cursor.execute(
                    "SELECT fee_collection_id FROM finance_fees WHERE id = %s",
                    (value,)
                )
                result = cursor.fetchone()
                cursor.close()
                if result:
                    fee_collection_id = result[0]
                    # Now lookup the fee_category_id from fee_collections
                    cursor = self.mysql_connection.cursor()
                    cursor.execute(
                        "SELECT fee_category_id FROM finance_fee_collections WHERE id = %s",
                        (fee_collection_id,)
                    )
                    result2 = cursor.fetchone()
                    cursor.close()
                    if result2:
                        fee_category_id = result2[0]
                        # Convert to UUID using the fee category mapping
                        return self.generate_uuid_for_fedena_id(fee_category_id, "finance_fee_categories")
                    else:
                        print(f"   ⚠️  Fee collection {fee_collection_id} not found, skipping record")
                        return None
                else:
                    print(f"   ⚠️  Finance fee {value} not found, skipping record")
                    return None
            except Exception as e:
                print(f"   ⚠️  Error looking up finance fee {value}: {e}, skipping record")
                return None

        elif transform_type == "json_field":
            # Convert to JSON string for PostgreSQL JSONField
            import json
            if value is None or value == "":
                return json.dumps({})
            if isinstance(value, str):
                try:
                    # Parse and re-serialize to ensure valid JSON
                    parsed = json.loads(value)
                    return json.dumps(parsed)
                except json.JSONDecodeError:
                    # If not valid JSON, wrap as raw value
                    return json.dumps({"raw_value": value})
            elif isinstance(value, dict):
                return json.dumps(value)
            else:
                # Convert other types to JSON
                return json.dumps({"value": str(value)})

        elif transform_type == "subject_name_to_uuid":
            # Look up subject UUID by name from already migrated subjects
            if value is None or value == "":
                return None

            cache = self._lookup_cache.setdefault("subject_name_to_uuid", {})
            if value in cache:
                return cache[value]

            resolved = None
            try:
                cursor = self.connection.cursor()

                # First try exact match
                cursor.execute(
                    "SELECT id FROM core_subject WHERE tenant_id = %s AND name = %s LIMIT 1",
                    (self.tenant_id, str(value))
                )
                result = cursor.fetchone()

                if not result:
                    # Try case-insensitive match
                    cursor.execute(
                        "SELECT id FROM core_subject WHERE tenant_id = %s AND LOWER(name) = LOWER(%s) LIMIT 1",
                        (self.tenant_id, str(value))
                    )
                    result = cursor.fetchone()

                if not result:
                    # Try partial match (first word)
                    first_word = str(value).split()[0] if str(value).split() else str(value)
                    cursor.execute(
                        "SELECT id FROM core_subject WHERE tenant_id = %s AND name ILIKE %s LIMIT 1",
                        (self.tenant_id, f"%{first_word}%")
                    )
                    result = cursor.fetchone()

                cursor.close()
                if result:
                    resolved = result[0]
            except Exception as e:
                print(f"   ⚠️  Error looking up subject '{value}': {e}")
                return None

            cache[value] = resolved
            return resolved

        elif transform_type == "yaml_to_json":
            # Convert YAML (especially Ruby YAML) to simple JSON
            import json
            import re
            if value is None or value == "":
                return json.dumps({})

            if isinstance(value, str):
                # Check if it's Ruby YAML
                if value.startswith("--- !ruby/object:"):
                    # Extract simple template info from Ruby YAML
                    template_info = {
                        "type": "ruby_template",
                        "source": "fedena",
                        "migrated": True
                    }

                    # Extract display_name safely
                    display_match = re.search(r'display_name:\s*([^\n\r]+)', value)
                    if display_match:
                        display_name = display_match.group(1).strip()
                        template_info["display_name"] = display_name

                    # Extract template name from object definition
                    object_match = re.search(r'!ruby/object:([^\s\n]+)', value)
                    if object_match:
                        template_info["object_type"] = object_match.group(1)

                    # Skip description extraction due to escaping issues
                    template_info["has_description"] = "description:" in value

                    return json.dumps(template_info)
                else:
                    # Try to parse as regular YAML or JSON
                    try:
                        import json
                        parsed = json.loads(value)
                        return json.dumps(parsed)
                    except json.JSONDecodeError:
                        return json.dumps({"migrated_content": "non_json_yaml"})

        elif transform_type == "create_default_period_entry":
            # Create a default PeriodEntry for attendance records
            # This assumes we have access to the current record context
            # For now, return a placeholder UUID that we'll create dynamically
            return "00000000-0000-4000-8000-000000000001"  # Placeholder for default period entry

        elif transform_type == "unique_course_code":
            if value is None:
                return "UNKNOWN"
            return str(value)

        elif transform_type == "finance_fee_id_to_student_uuid":
            # Derive student_id from the already-migrated core_financefee record.
            if value is None:
                return None
            try:
                fee_uuid = self.generate_uuid_for_fedena_id(int(value), "finance_fees")
                cursor = self.connection.cursor()
                cursor.execute('SELECT student_id FROM core_financefee WHERE id = %s', (fee_uuid,))
                result = cursor.fetchone()
                cursor.close()
                return str(result[0]) if result and result[0] else None
            except Exception as e:
                return None

        elif transform_type == "finance_fee_id_to_category_uuid":
            # Derive fee_category_id from the already-migrated core_financefee record.
            if value is None:
                return None
            try:
                fee_uuid = self.generate_uuid_for_fedena_id(int(value), "finance_fees")
                cursor = self.connection.cursor()
                cursor.execute('SELECT fee_category_id FROM core_financefee WHERE id = %s', (fee_uuid,))
                result = cursor.fetchone()
                cursor.close()
                return str(result[0]) if result and result[0] else None
            except Exception as e:
                return None

        elif transform_type == "finance_transaction_id_to_amount":
            # Derive amount from the already-migrated core_financetransaction record.
            if value is None:
                return 0.0
            try:
                txn_uuid = self.generate_uuid_for_fedena_id(int(value), "finance_transactions")
                cursor = self.connection.cursor()
                cursor.execute('SELECT amount FROM core_financetransaction WHERE id = %s', (txn_uuid,))
                result = cursor.fetchone()
                cursor.close()
                return float(result[0]) if result and result[0] is not None else 0.0
            except Exception as e:
                return 0.0

        elif transform_type == "finance_transaction_id_to_date":
            # Derive payment_date from the already-migrated core_financetransaction record.
            if value is None:
                return None
            try:
                txn_uuid = self.generate_uuid_for_fedena_id(int(value), "finance_transactions")
                cursor = self.connection.cursor()
                cursor.execute('SELECT transaction_date FROM core_financetransaction WHERE id = %s', (txn_uuid,))
                result = cursor.fetchone()
                cursor.close()
                if result and result[0]:
                    d = result[0]
                    return d.date().isoformat() if hasattr(d, 'date') else str(d)
                return None
            except Exception as e:
                return None

        return value


    def transform_table(
        self, fedena_table: str, target_table: Optional[str] = None
    ) -> bool:
        if fedena_table not in FedenaTableMapping.FIELD_MAPPINGS:
            print(f"⚠️  No mapping configuration for table: {fedena_table}")
            return False

        table_config = FedenaTableMapping.FIELD_MAPPINGS[fedena_table]
        # Default the source table to the mapping key, but DON'T clobber an explicit
        # "source_table" (e.g. guardians_as_relations reads from the guardians table).
        table_config.setdefault("source_table", fedena_table)
        target_model = target_table or table_config["target_model"]

        print(f"\n🔄 Transforming table: {fedena_table} -> {target_model}")

        try:
            source_table = table_config.get("source_table", fedena_table)
            # Use MySQL connection if available, otherwise fall back to SQL file parsing
            if self.mysql_connection:
                filters = table_config.get("filters", [])
                records = self.fetch_mysql_table_data(source_table, filters)
            else:
                records = self.parse_fedena_table_data(source_table)

            if not records:
                print(f"   ℹ️  No data found for table {fedena_table}")
                return True

            # For MySQL connections, filters are applied at SQL level
            # For file parsing, we still need Python-level filtering
            if "filters" in table_config and not self.mysql_connection:
                original_count = len(records)
                for filter_condition in table_config["filters"]:
                    if "is_deleted = 0" in filter_condition:
                        records = [
                            r for r in records if r.get("is_deleted") in (0, "0", None)
                        ]
                    elif "is_deleted = 0 OR is_deleted IS NULL" in filter_condition:
                        records = [
                            r for r in records if r.get("is_deleted") in (0, "0", None, "")
                        ]
                    elif "IS NOT NULL" in filter_condition:
                        # Extract field name from condition like "student_id IS NOT NULL"
                        field_name = filter_condition.split(" IS NOT NULL")[0].strip()
                        records = [
                            r for r in records if r.get(field_name) is not None and r.get(field_name) != "" and r.get(field_name) != "NULL"
                        ]
                    elif "IS NULL" in filter_condition and "IS NOT NULL" not in filter_condition:
                        # Extract field name from condition like "field IS NULL"
                        field_name = filter_condition.split(" IS NULL")[0].strip()
                        records = [
                            r for r in records if r.get(field_name) is None or r.get(field_name) == "" or r.get(field_name) == "NULL"
                        ]
                    elif 'name IS NOT NULL AND name != ""' in filter_condition:
                        records = [
                            r for r in records if r.get("name") is not None and r.get("name") != "" and r.get("name") != "NULL"
                        ]
                    elif 'mobile_number IS NOT NULL AND mobile_number != "" AND mobile_number != "NULL"' in filter_condition:
                        records = [
                            r for r in records if r.get("mobile_number") is not None and r.get("mobile_number") != "" and r.get("mobile_number") != "NULL"
                        ]
                print(f"   📝 Applied filters: {original_count} -> {len(records)} records")
            elif "filters" in table_config and self.mysql_connection:
                print(f"   📝 Applied filters at SQL level -> {len(records)} records")

            # Pre-dedupe on a globally/compositely unique natural key so a second
            # source row with the same key can't silently fail to insert. Keep the
            # lowest-id row (mirrors the courses MIN(id) GROUP BY code filter).
            dedupe_key = table_config.get("dedupe_key")
            if dedupe_key:
                before = len(records)
                seen: Dict[Any, Dict[str, Any]] = {}
                for r in records:
                    k = r.get(dedupe_key)
                    if k in (None, "", "NULL"):
                        seen[f"__nokey_{id(r)}"] = r
                        continue
                    existing = seen.get(k)
                    if existing is None:
                        seen[k] = r
                    else:
                        current_id = self._as_int(r.get("id"))
                        existing_id = self._as_int(existing.get("id"))
                        if current_id < existing_id:
                            # Current record is the new keeper, old existing is dropped
                            self._dedupe_id_mappings[str(existing.get("id"))] = str(r.get("id"))
                            seen[k] = r
                        else:
                            # Existing record remains the keeper, current record is dropped
                            self._dedupe_id_mappings[str(r.get("id"))] = str(existing.get("id"))
                records = list(seen.values())
                dropped = before - len(records)
                if dropped:
                    print(f"   🧹 De-duplicated on {dedupe_key}: {before} -> {len(records)} ({dropped} source rows dropped)")
                    self.stats["duplicates"].append(
                        f"{fedena_table}: {dropped} source rows dropped as duplicate {dedupe_key}"
                    )

            # Transform + validate every record up front, buffering the survivors so
            # they can be inserted in batches. FK validation happens here (not in the
            # batch) so one bad row can never poison an otherwise-good chunk.
            #
            # orphan_skipped = rows skipped because a parent FK isn't present (dangling
            # references — common in Fedena dumps). These are expected data-quality
            # skips, NOT migration failures, so they are excluded from the error-rate
            # denominator below; otherwise a handful of orphans would roll back an
            # otherwise-healthy table and discard all the valid rows with them.
            buffer: List[Dict[str, Any]] = []
            orphan_skipped = 0
            for record in records:
                try:
                    transformed_record = self.transform_record(record, table_config)

                    # Skip records that couldn't be transformed (missing required fields)
                    if transformed_record is None:
                        continue

                    if target_model == "core_batchstudent":
                        if not transformed_record.get("student_id") or not transformed_record.get("batch_id"):
                            missing = "student_id" if not transformed_record.get("student_id") else "batch_id"
                            print(
                                f"   ⚠️  Skipping batch_student record {record.get('id')}: {missing} not found in id_mappings"
                            )
                            orphan_skipped += 1
                            continue

                    # FK validation hits the DB; skip it in dry-run (matches the old
                    # insert path) so dry-run still reports meaningful per-table counts.
                    if not self.dry_run and table_config and not self.validate_foreign_keys(transformed_record, table_config):
                        # validate_foreign_keys already records the reason; this is an
                        # orphaned reference, not a migration error.
                        orphan_skipped += 1
                        continue

                    buffer.append(transformed_record)
                except Exception as e:
                    self.stats["errors"].append(
                        f"Error transforming record {record.get('id')} in {fedena_table}: {e}"
                    )
                    print(
                        f"   ✗ Error transforming record {record.get('id')} in {fedena_table}: {e}"
                    )

            if orphan_skipped:
                print(f"   ↪️  Skipped {orphan_skipped} record(s) with missing parent references (orphans)")
                self.stats.setdefault("skipped", []).append(
                    f"{fedena_table}: {orphan_skipped} orphaned rows skipped (missing parent FK)"
                )

            batch_size = table_config.get("batch_size", 1000)
            success_count = self._flush_records(buffer, target_model, table_config, batch_size)

            print(f"   ✓ Transformed {success_count}/{len(records)} records")

            if not self.dry_run:
                # Error rate is computed over records we actually ATTEMPTED to insert
                # (i.e. excluding orphan skips), so dangling source references don't
                # trip the rollback and discard the valid rows.
                considered = len(records) - orphan_skipped
                error_count = considered - success_count
                error_rate = error_count / considered if considered else 0
                if error_rate > self.max_error_rate and considered > 10:
                    self.connection.rollback()
                    msg = (f"Table {fedena_table} rolled back — error rate "
                           f"{error_rate:.1%} exceeds threshold {self.max_error_rate:.1%} "
                           f"({error_count}/{len(records)} records failed)")
                    print(f"   ✗ {msg}")
                    self.stats["errors"].append(msg)
                    return False
                self.connection.commit()
                if error_count > 0:
                    print(f"   ⚠️  Committed {success_count} records ({error_count} skipped, error rate {error_rate:.1%})")

            self.stats["records_transformed"] += success_count
            self.stats["tables_processed"] += 1
            return success_count > 0

        except Exception as e:
            if not self.dry_run and self.connection:
                self.connection.rollback()
            print(f"   ✗ Transformation failed: {e}")
            self.stats["errors"].append(f"Error transforming table {fedena_table}: {e}")
            return False

    def transform_record(
        self, record: Dict[str, Any], table_config: Dict
    ) -> Dict[str, Any]:
        """Transform a single record according to field mappings."""
# Debug removed

        transformed = {}

       # --- ADD THIS BLOCK ---
        # 1. Remap dropped FK IDs to their surviving counterparts (fixes dedupe orphans)
        for field_name, field_value in list(record.items()):
            if field_name.endswith("_id") and str(field_value) in self._dedupe_id_mappings:
                record[field_name] = self._dedupe_id_mappings[str(field_value)]

                    # 2. Treat 0 or "0" as None for foreign keys (common Fedena quirk)
            if field_name.endswith("_id") and field_value in (0, "0", 0.0):
                record[field_name] = None

        # Add tenant context if required
        if table_config.get("tenant_field"):
            transformed["tenant_id"] = self.tenant_id

        # NOTE: relationship/junction records that have no Fedena integer id get a
        # DETERMINISTIC id assigned in the model-specific post-processing below
        # (keyed on their natural FK pair). A random uuid4 here would mint a new id
        # every run and duplicate the row on every re-run.

        # Transform each mapped field
        for source_field, target_config in table_config["fields"].items():
            if source_field in record:
                value = record[source_field]
# Debug removed

                # Use default if value is None or empty
                if (value is None or value == "" or value == "NULL") and "default" in target_config:
                    value = target_config["default"]

                # Apply transformation if specified
                if "transform" in target_config:
                    # For foreign key transformations, use the correct source table
                    if target_config["transform"] == "fedena_id_to_uuid" and target_config[
                        "target"
                    ].endswith("_id"):
                        # Map foreign key field names to their source tables
                        fk_source_table_map = {
                            "course_id": "courses",
                            "academic_year_id": "academic_years",
                            "student_id": "students",
                            "employee_id": "employees",
                            "class_teacher_id": "employees",  # maps to employee_id in target
                            "batch_id": "batches",
                            "finance_fee_id": "finance_fees",
                            "fee_category_id": "finance_fee_categories",
                            "grade_set_id": "cce_grade_sets",
                            "report_id": "reports",
                            "notification_id": "notifications",
                            "batch_event_id": "batch_events",
                            "online_exam_group_id": "online_exam_groups",
                            "question_id": "online_exam_questions",
                            "attempt_id": "online_exam_attempts",
                            "assessment_group_id": "assessment_groups",
                            "subject_id": "subjects",
                            "guardian_id": "guardians",
                            "category_id": "finance_transaction_categories",
                            "fee_category_id": "finance_fee_categories",
                            "finance_transaction_id": "finance_transactions",
                            "transaction_receipt_id": "transaction_receipts",
                            "fee_account_id": "fee_accounts",
                            "fee_receipt_template_id": "fee_templates",
                            "exam_group_id": "exam_groups",
                            "grading_level_id": "grading_levels",
                            "weekday_id": "weekday_sets",
                            "class_timing_id": "class_timings",
                            "attendance_label_id": "attendance_labels",
                            "additional_field_id": "additional_fields",
                            "elective_group_id": "elective_groups",
                            "skill_set_id": "subject_skill_sets",
                        }

                        # Use the mapped source table for foreign keys
                        fk_source_table = fk_source_table_map.get(
                            target_config["target"], table_config.get("source_table")
                        )
                        value = self.transform_field_value(
                            value, target_config["transform"], fk_source_table
                        )
                    else:
                        # Use current table for non-foreign key transformations
                        value = self.transform_field_value(
                            value,
                            target_config["transform"],
                            table_config.get("source_table"),
                        )

                transformed[target_config["target"]] = value
            elif "default" in target_config:
                # Use default if field is missing entirely
                transformed[target_config["target"]] = target_config["default"]
            else:
                # Field not found in source record, but that's OK for partial mappings
                continue

        # Handle custom mappings (where source field differs from target field)
        if "custom_mappings" in table_config:
            for target_field, mapping_config in table_config["custom_mappings"].items():
                source_field = mapping_config["source"]
                if source_field in record:
                    value = record[source_field]

                    # Apply transformation if specified
                    if "transform" in mapping_config:
                        value = self.transform_field_value(
                            value,
                            mapping_config["transform"],
                            table_config.get("source_table"),
                        )

                    transformed[target_field] = value

        # Apply table-level default values
        if "default_values" in table_config:
            for field_name, default_value in table_config["default_values"].items():
                if field_name not in transformed:
                    transformed[field_name] = default_value

        # Check for required foreign key fields - skip record if critical fields are null
        if table_config.get("target_model") == "core_coursesubject":
            if not transformed.get("id") or not transformed.get("subject_id"):
                print(f"   ⚠️  Skipping course_subject record - missing required fields (id: {transformed.get('id')}, subject_id: {transformed.get('subject_id')})")
                return None

        if table_config.get("target_model") == "core_employeesubject":
            if not transformed.get("id") or not transformed.get("employee_id"):
                return None

        # UNIVERSAL DATA PRESERVATION: Handle missing required fields for ALL models
        target_model = table_config.get("target_model")
        transformed = self.ensure_all_required_fields(transformed, target_model)

        # Some relation models carry a required (NOT NULL) `school` FK that has no
        # corresponding source column in Fedena. In this schema the School *is* the
        # tenant (both `tenant` and `school` FKs point at the same School row), so
        # school_id == tenant_id. Without this every insert fails the NOT NULL
        # constraint and the whole table rolls back.
        SCHOOL_REQUIRED_MODELS = {"core_studentguardianrelation"}
        if target_model in SCHOOL_REQUIRED_MODELS and not transformed.get("school_id"):
            transformed["school_id"] = self.tenant_id

        # Deterministic ids for junction/relation records that have no Fedena
        # integer id of their own. Keyed on the natural FK pair so the same logical
        # row always maps to the same UUID — making re-runs idempotent under
        # ON CONFLICT (id) DO NOTHING.
        if not transformed.get("id"):
            if target_model == "core_studentguardianrelation":
                transformed["id"] = self.deterministic_id(
                    target_model,
                    transformed.get("student_id"),
                    transformed.get("guardian_id"),
                )
            elif target_model == "core_userprivilege":
                transformed["id"] = self.deterministic_id(
                    target_model,
                    transformed.get("user_id"),
                    transformed.get("privilege_id"),
                )

        # Exam post-processing: populate exam_name from subject name if not set
        if target_model == "core_exam" and not transformed.get("exam_name"):
            # Try to look up the subject name from the DB using the mapped subject_id
            subject_id = transformed.get("subject_id")
            if subject_id:
                try:
                    import django
                    from django.apps import apps
                    Subject = apps.get_model("core", "Subject")
                    subj = Subject.objects.filter(id=subject_id).first()
                    if subj:
                        transformed["exam_name"] = subj.name
                except Exception:
                    pass

        # SkillSet post-processing: derive unique code from name
        if target_model == "core_skillset":
            import re as _re
            raw = transformed.get("name", "") or ""
            code = _re.sub(r'[^A-Z0-9_]', '', raw.upper().replace(" ", "_").replace("-", "_"))
            transformed["code"] = (code[:48] if code else "SKL") + "_" + str(transformed.get("id", ""))[:2]

        # Fee transaction post-processing — must run after defaults are applied
        if target_model == "core_feetransaction":
            if not transformed.get("transaction_date"):
                d = transformed.get("created_at")
                if d:
                    transformed["transaction_date"] = d.date().isoformat() if hasattr(d, "date") else str(d)[:10]

        # Model-specific data quality fixes
        if target_model == "core_student":
            adm = transformed.get("admission_no", "<no admission_no>")
            if not transformed.get("last_name"):
                first = transformed.get("first_name", "")
                if first:
                    # Single-name student — duplicate first_name into last_name so the
                    # required field is satisfied without hiding the gap behind "Student".
                    transformed["last_name"] = first
                    self.stats.setdefault("warnings", []).append(
                        f"Student {adm}: last_name was empty, set to first_name ({first!r})"
                    )
                else:
                    # Neither name present — flag loudly rather than inserting a
                    # meaningless placeholder.
                    transformed["last_name"] = "UNKNOWN"
                    transformed["first_name"] = "UNKNOWN"
                    self.stats.setdefault("warnings", []).append(
                        f"Student {adm}: both first_name and last_name were empty"
                    )
            if not transformed.get("first_name"):
                self.stats.setdefault("warnings", []).append(
                    f"Student {adm}: first_name was empty"
                )

            # Generate unique admission_no only if missing, using deterministic ID-based approach
            if not transformed.get("admission_no"):
                student_id = transformed.get("id", "")
                if student_id:
                    # Use last 8 chars of UUID for readability
                    transformed["admission_no"] = f"MIGRATED-{student_id[-8:].upper()}"
                else:
                    transformed["admission_no"] = f"MIGRATED-{uuid.uuid4().hex[:8].upper()}"

        elif target_model == "core_batch":
            # Generate batch name from course and year if missing
            if not transformed.get("name"):
                course_info = transformed.get("course_id", "Course")
                year_info = transformed.get("academic_year_id", "Year")
                transformed["name"] = f"Batch-{course_info}-{year_info}"[:255]

        elif target_model == "core_classtiming":
            # Provide default time periods if missing
            if not transformed.get("start_time"):
                transformed["start_time"] = "08:00:00"
            if not transformed.get("end_time"):
                transformed["end_time"] = "09:00:00"

        elif target_model == "core_gradingtype":
            # Generate unique code from name + fedena ID to handle duplicates
            if not transformed.get("code") and transformed.get("name"):
                grade_name = str(transformed["name"]).upper()
                # Clean up the name for code use
                import re
                code = re.sub(r'[^A-Z0-9]', '', grade_name)
                if not code:
                    code = "GRADE"
                # Add fedena ID suffix to ensure uniqueness
                fedena_id = record.get("id", "")
                unique_code = f"{code}_{fedena_id}"[:20]  # Limit to 20 chars
                transformed["code"] = unique_code

        # Set default timestamps if not present
        if "created_at" not in transformed:
            transformed["created_at"] = datetime.now()
        if "updated_at" not in transformed:
            transformed["updated_at"] = datetime.now()

        # Idempotency guard (runs AFTER the deterministic-id assignment above):
        # every record must carry a deterministic id so ON CONFLICT (id) DO NOTHING
        # makes re-runs safe. A record without an id would get a fresh DB-generated
        # UUID each run and duplicate on every re-run — skip and surface it instead.
        if not transformed.get("id"):
            self.stats.setdefault("errors", []).append(
                f"Skipped {table_config.get('target_model')} record: no deterministic "
                f"id produced (mapping must map an id or define a natural-key id rule)"
            )
            print(f"   ⚠️  Skipping {table_config.get('target_model')} record — no id (would duplicate on re-run)")
            return None

        return transformed

    def _get_first_id(self, cache_key: str, sql: str, params: Tuple) -> Optional[str]:
        """Memoized "first available row id" lookup.

        These fallbacks are queried for many records; the value doesn't change once a
        non-null row exists, so caching turns thousands of identical SELECTs into one.
        A None result is NOT cached, so the value is picked up once that table is
        populated later in the same run.
        """
        if self._first_id_cache.get(cache_key):
            return self._first_id_cache[cache_key]
        try:
            cursor = self.connection.cursor()
            cursor.execute(sql, params)
            result = cursor.fetchone()
            cursor.close()
            value = result[0] if result else None
        except Exception as e:
            print(f"Error getting {cache_key}: {e}")
            return None
        if value:
            self._first_id_cache[cache_key] = value
        return value

    def get_first_course_id(self) -> Optional[str]:
        return self._get_first_id(
            "first_course_id",
            "SELECT id FROM core_course WHERE tenant_id = %s LIMIT 1",
            (self.tenant_id,),
        )

    def get_first_academic_year_id(self) -> Optional[str]:
        return self._get_first_id(
            "first_academic_year_id",
            "SELECT id FROM core_academicyear WHERE tenant_id = %s LIMIT 1",
            (self.tenant_id,),
        )

    def get_first_country_id(self) -> Optional[str]:
        return self._get_first_id(
            "first_country_id",
            "SELECT id FROM core_country LIMIT 1",
            (),
        )

    def get_first_batch_id(self) -> Optional[str]:
        return self._get_first_id(
            "first_batch_id",
            "SELECT id FROM core_batch WHERE tenant_id = %s LIMIT 1",
            (self.tenant_id,),
        )

    def ensure_all_required_fields(
        self, transformed: Dict[str, Any], target_model: str
    ) -> Dict[str, Any]:
        # Model-specific required field defaults (only for fields that exist in each model)
        model_required_defaults = {
            "core_news": {
                "title": "Migrated News",
                "content": "Migrated content from Fedena",
                "author": "System",
                "is_active": True,
            },
            "core_additionalfield": {
                "name": "Migrated Field",
                "is_mandatory": False,
                "input_type": "text",
            },
            "core_timezone": {
                "name": "Migrated Timezone",
                "zone": "UTC",
            },
            "core_weekday": {
                "weekday": "Monday",
                "day_of_week": 1,
            },
            "core_weekdaysetweekday": {
                # No required fields with defaults needed
            },
            "core_studentcategory": {
                "name": "Migrated Category",
                "is_deleted": False,
            },
            "core_employeedepartment": {
                "name": "Migrated Department",
                "code": f"DEPT-{uuid.uuid4().hex[:4].upper()}",
                "status": True,
            },
            "core_attendancelabel": {
                "name": "Attendance Status",
                "code": f"ATT-{uuid.uuid4().hex[:4].upper()}",
                "color_code": "#808080",
                "is_active": True,
            },
            "core_employeecategory": {
                "name": "Migrated Category",
                "prefix": "EMP",
                "status": True,
            },
            "core_report": {
                "name": "Migrated Report",
                "is_active": True,
            },
            "core_course": {
                "course_name": "Unnamed Course",
                "code": f"COURSE-{uuid.uuid4().hex[:6].upper()}",
                "is_deleted": False,
                "grading_type": "percentage",
                "max_hours_day": 8,
                "max_hours_week": 40,
            },
            "core_guardian": {
                "first_name": "Unknown",
                "last_name": "Guardian",
                "email": "unknown@example.com",
                "mobile_phone": "000-000-0000",
                "is_active": True,
            },
            "core_user": {
                "username": f"user_{uuid.uuid4().hex[:8]}",
                "first_name": "Unknown",
                "last_name": "User",
                "email": f"user_{uuid.uuid4().hex[:8]}@example.com",
                "is_active": True,
            },
            "core_classtiming": {
                "name": "Class Period",
                "start_time": "08:00:00",
                "end_time": "09:00:00",
                "is_break": False,
                "is_deleted": False,
            },
            "core_smslog": {
                "mobile_number": "000-000-0000",
                "message": "Migrated SMS log",
                "status": "migrated",
                "is_active": True,
            },
            "core_privilege": {
                "name": "Migrated Privilege",
                "is_active": True,
            },
            "core_employeeposition": {
                "name": "Migrated Position",
                "status": True,
            },
            "core_student": {
                # Don't set admission_no default here - use dynamic generation
                # NOTE: first_name/last_name intentionally omitted — missing names are
                # handled below via the first_name_as_last_name fallback and a warning
                # log so they are surfaced rather than silently replaced with placeholders.
                "has_paid_fees": False,
                "is_active": True,
                "gender": "other",  # String field, not boolean
                "blood_group": "Unknown",
                "date_of_birth": date(2000, 1, 1),
                "admission_date": date.today(),
            },
            "core_academicyear": {
                "name": "Migrated Academic Year",
                "start_date": date.today(),
                "end_date": date.today() + timedelta(days=365),
                "is_active": True,
            },
            "core_employeegrade": {
                "name": "Migrated Grade",
                "status": True,
                "priority": 1,
                "max_hours_day": 8,
                "max_hours_week": 40,
            },
            "core_archivedstudent": {
                "admission_no": f"ARCH-{uuid.uuid4().hex[:8].upper()}",
                "first_name": "Unknown",
                "last_name": "Archived Student",
                "status_description": "Migrated from Fedena",
                # Note: gender and date_of_birth fields don't exist in ArchivedStudent model
            },
            "core_financialyear": {
                "name": "Migrated Financial Year",
                "start_date": date.today(),
                "end_date": date.today() + timedelta(days=365),
                "is_active": True,
            },
            "core_employee": {
                "employee_number": f"EMP-{uuid.uuid4().hex[:8].upper()}",
                "first_name": "Unknown",
                "last_name": "Employee",
                "status": True,
                "gender": False,  # Boolean field: False=Female, True=Male
                "blood_group": "Unknown",
                "marital_status": "Unknown",
                "qualification": "Not Specified",
                "joining_date": date.today(),
                "experience_year": 0,
                "experience_month": 0,
                "children_count": 0,
            },
            "core_batch": {
                "name": f"Batch-{uuid.uuid4().hex[:8].upper()}",
                "is_active": True,
            },
            "core_book": {
                "title": "Unknown Title",
                "author": "Unknown Author",
                "is_active": True,
            },
            "core_feetransaction": {
                "transaction_type": "FEE_PAYMENT",
                "amount": 0.0,
                "transaction_date": "2024-01-01",
            },
        }

        # No universal defaults - use model-specific only

        model_specific_defaults = {
            "core_student": {
                # admission_no handled in model-specific logic above
                # first_name/last_name intentionally omitted — see model_required_defaults
                "has_paid_fees": False,
            },
            "core_employee": {
                "employee_number": f"EMP-{uuid.uuid4().hex[:8].upper()}",
                "first_name": "Unknown",
                "last_name": "Employee",
            },
            "core_course": {
                "course_name": "Unnamed Course",
                "code": f"COURSE-{uuid.uuid4().hex[:6].upper()}",
            },
            "core_batch": {
                "name": f"Batch-{uuid.uuid4().hex[:8].upper()}",
            },
            "core_classtiming": {
                "name": "Class Period",
            },
            "core_attendancelabel": {
                "name": "Attendance Status",
                "code": f"ATT-{uuid.uuid4().hex[:4].upper()}",
                "color_code": "#808080",
            },
            "core_smslog": {
                "mobile_number": "000-000-0000",
                "message": "Migrated SMS log",
                "status": "migrated",
            },
        }

        # Apply model-specific required defaults first
        if target_model in model_required_defaults:
            for field, default_value in model_required_defaults[target_model].items():
                if transformed.get(field) is None or transformed.get(field) == "":
                    transformed[field] = default_value

        # Always set unusable password for migrated users — Fedena uses Rails bcrypt,
        # which is incompatible with Django's PBKDF2. Users must use forgot-password
        # to set a new password after migration.
        if target_model == "core_user":
            transformed["password"] = "!"

        # No universal defaults applied

        # Apply legacy model-specific defaults
        if target_model in model_specific_defaults:
            for field, default_value in model_specific_defaults[target_model].items():
                if field in [
                    "admission_no",
                    "employee_number",
                    "course_name",
                    "name",
                    "first_name",
                    "last_name",
                    "has_paid_fees",
                ]:
                    if (
                        field not in transformed
                        or transformed.get(field) is None
                        or transformed.get(field) == ""
                    ):
                        transformed[field] = default_value
                elif field in transformed and (
                    transformed.get(field) is None or transformed.get(field) == ""
                ):
                    transformed[field] = default_value

        if target_model == "core_batch":
            if not transformed.get("course_id"):
                first_course_id = self.get_first_course_id()
                if first_course_id:
                    transformed["course_id"] = first_course_id
                    print(
                        f"   ⚠️  Assigned default course to batch {transformed.get('name', 'Unknown')}"
                    )
                else:
                    raise ValueError("No courses available for batch assignment")
            if not transformed.get("academic_year_id"):
                first_academic_year_id = self.get_first_academic_year_id()
                if first_academic_year_id:
                    transformed["academic_year_id"] = first_academic_year_id
                    print(
                        f"   ⚠️  Assigned default academic year to batch {transformed.get('name', 'Unknown')}"
                    )
                else:
                    raise ValueError("No academic years available for batch assignment")

        elif target_model == "core_student":
            if not transformed.get("nationality_id"):
                first_country_id = self.get_first_country_id()
                if first_country_id:
                    transformed["nationality_id"] = first_country_id

        elif target_model == "core_classtiming":
            if not transformed.get("batch_id"):
                first_batch_id = self.get_first_batch_id()
                if first_batch_id:
                    transformed["batch_id"] = first_batch_id

        elif target_model == "core_batchstudent":
            if "is_active" not in transformed:
                transformed["is_active"] = True

        # Truncate string fields to prevent length errors
        for field, value in transformed.items():
            if isinstance(value, str):
                if field in [
                    "first_name",
                    "middle_name",
                    "last_name",
                    "admission_no",
                    "class_roll_no",
                    "address_line1",
                    "address_line2",
                    "city",
                    "state",
                    "pin_code",
                    "phone1",
                    "phone2",
                    "email",
                    "language",
                    "religion",
                    "blood_group",
                    "birth_place",
                ]:
                    if len(value) > 100:
                        transformed[field] = value[:100]
                        print(
                            f"   ⚠️  Truncated {field} to 100 characters for record {transformed.get('id', 'Unknown')}"
                        )
                elif field not in [
                    # Fields declared as TextField in models.py — no length limit
                    "actual_mark", "description", "content", "body", "message",
                    "receipt_data", "report", "report_component", "configuration",
                    "remark_text", "question_text", "explanation", "additional_info",
                    "status_description", "remarks",
                ] and len(value) > 255:
                    transformed[field] = value[:255]
                    print(
                        f"   ⚠️  Truncated {field} to 255 characters for record {transformed.get('id', 'Unknown')}"
                    )

        if not transformed.get("created_at"):
            transformed["created_at"] = datetime.now()
        if not transformed.get("updated_at"):
            transformed["updated_at"] = datetime.now()

        # FINAL FIX: Auto-assign missing foreign keys for 100% success
        self.fix_missing_foreign_keys_universal(transformed, target_model)

        return transformed

    def fix_missing_foreign_keys_universal(self, transformed: Dict[str, Any], target_model: str):
        """Fill blank FK columns with a "first available" fallback.

        Only resolves a fallback for an FK the record actually has and that is
        currently empty — so the getters (each memoized) fire at most once per kind,
        instead of running 4 SELECTs for every record of every table.
        """
        fallback_getters = {
            "course_id": self.get_first_course_id,
            "academic_year_id": self.get_first_academic_year_id,
            "batch_id": self.get_first_batch_id,
            "country_id": self.get_first_country_id,
        }

        for field_name, getter in fallback_getters.items():
            if field_name in transformed and not transformed[field_name]:
                fallback_value = getter()
                if fallback_value:
                    transformed[field_name] = fallback_value
                    print(f"   🔧 Auto-fixed {field_name} with fallback value")

    @staticmethod
    def _as_int(value: Any) -> int:
        """Best-effort int for id comparison; unparseable ids sort last."""
        try:
            return int(value)
        except (TypeError, ValueError):
            return sys.maxsize

    def _conflict_clause(self, target_table: str, columns: List[str]) -> str:
        """ON CONFLICT clause shared by the batch and per-row insert paths.

        Deterministic ids mean a re-run conflicts on the PK and is skipped — that's
        what makes the migration idempotent. core_user is upserted on username
        because users may arrive from both `users` and `admin_users`.
        """
        if target_table == "core_user":
            update_cols = [c for c in columns if c not in ("id", "username", "password")]
            if update_cols:
                sets = ", ".join(f'"{c}" = EXCLUDED."{c}"' for c in update_cols)
                return f"ON CONFLICT (username) DO UPDATE SET {sets}"
            return "ON CONFLICT (username) DO NOTHING"
        return "ON CONFLICT (id) DO NOTHING"

    # PostgreSQL data_type values that accept a plain string (so "" is a valid value).
    # Everything else (numeric/integer/date/timestamp/boolean/uuid/json) rejects "" and
    # needs NULL instead — the classic MySQL-empty-string → PostgreSQL hazard.
    _TEXT_PG_TYPES = {
        "character varying", "varchar", "text", "character", "char", "bpchar",
        "citext", "name",
    }

    def _column_types(self, target_table: str) -> Dict[str, str]:
        """{column_name: data_type} for a target table, read once from information_schema."""
        if target_table in self._table_columns_cache:
            return self._table_columns_cache[target_table]
        types: Dict[str, str] = {}
        try:
            cur = self.connection.cursor()
            cur.execute(
                "SELECT column_name, data_type FROM information_schema.columns WHERE table_name = %s",
                (target_table,),
            )
            types = {row[0]: row[1] for row in cur.fetchall()}
            cur.close()
        except Exception as e:
            print(f"   ⚠️  Could not read columns for {target_table}: {e}")
        self._table_columns_cache[target_table] = types
        return types

    def _sanitize_for_table(self, buffer: List[Dict[str, Any]], target_table: str) -> None:
        """Make buffered records safe to INSERT into the real table:

        1. Drop mapped keys that aren't real columns (a mapping pointing at a column the
           model doesn't have would make EVERY insert fail and roll the whole table back).
        2. Coerce empty-string "" → None for non-text columns (numeric/date/uuid/etc.),
           because MySQL stores "" where PostgreSQL requires NULL — otherwise valid rows
           fail with e.g. 'invalid input syntax for type numeric: ""'.

        Both are safe: phantom columns are never required model fields, and "" was never a
        valid value for a numeric/date column. Dropped columns are logged.
        """
        types = self._column_types(target_table)
        if not types:  # couldn't introspect — leave records untouched
            return
        unknown = set()
        for rec in buffer:
            for k in list(rec.keys()):
                dtype = types.get(k)
                if dtype is None:
                    unknown.add(k)
                    del rec[k]
                    continue
                if rec[k] == "" and dtype not in self._TEXT_PG_TYPES:
                    rec[k] = None
        if unknown:
            msg = f"{target_table}: dropped mapped columns not on model: {sorted(unknown)}"
            print(f"   ⚠️  {msg}")
            self.stats.setdefault("schema_mismatches", []).append(msg)

    def _flush_records(self, buffer: List[Dict[str, Any]], target_table: str,
                       table_config: Dict, batch_size: int) -> int:
        """Insert buffered records in batches; returns the count successfully stored
        (rows skipped by an id-conflict on re-run count as success)."""
        if self.dry_run:
            return len(buffer)
        if not buffer:
            return 0
        # Drop phantom columns and coerce ""→NULL for non-text columns.
        self._sanitize_for_table(buffer, target_table)
        if not batch_size or batch_size < 1:
            batch_size = 1000
        inserted = 0
        for start in range(0, len(buffer), batch_size):
            chunk = buffer[start:start + batch_size]
            inserted += self._insert_chunk(chunk, target_table, table_config)
        return inserted

    def _insert_chunk(self, chunk: List[Dict[str, Any]], target_table: str,
                      table_config: Dict) -> int:
        """Batch-insert a chunk via execute_values. On any batch failure, fall back
        to per-row inserts for that group so one bad row can't lose the batch and
        unique collisions get classified as duplicates rather than hidden."""
        from collections import defaultdict
        # execute_values needs a uniform column set, but records can differ in which
        # optional fields are present — group by their exact column set.
        groups: Dict[Tuple[str, ...], List[Dict[str, Any]]] = defaultdict(list)
        for rec in chunk:
            groups[tuple(sorted(rec.keys()))].append(rec)

        inserted = 0
        cursor = self.connection.cursor()
        for col_key, recs in groups.items():
            columns = list(col_key)
            column_names = ", ".join(f'"{c}"' for c in columns)
            conflict = self._conflict_clause(target_table, columns)
            sql = f'INSERT INTO "{target_table}" ({column_names}) VALUES %s {conflict}'
            rows = [[r.get(c) for c in columns] for r in recs]

            cursor.execute("SAVEPOINT sp_batch")
            try:
                execute_values(cursor, sql, rows, page_size=len(rows))
                cursor.execute("RELEASE SAVEPOINT sp_batch")
                inserted += len(recs)
            except Exception:
                cursor.execute("ROLLBACK TO SAVEPOINT sp_batch")
                for r in recs:
                    if self.insert_transformed_record(r, target_table, table_config):
                        inserted += 1
        cursor.close()
        return inserted

    def insert_transformed_record(self, record: Dict[str, Any], target_table: str, table_config: Dict = None) -> bool:
        """Insert a single record (per-row fallback path for batch failures)."""
        if self.dry_run:
            return True

        # Validate foreign keys if table config provided
        if table_config and not self.validate_foreign_keys(record, table_config):
            return False

        try:
            cursor = self.connection.cursor()

            # Build INSERT statement
            columns = list(record.keys())
            values = list(record.values())

            column_names = ', '.join([f'"{col}"' for col in columns])
            placeholders = ', '.join(['%s'] * len(values))

            insert_sql = (
                f'INSERT INTO "{target_table}" ({column_names}) VALUES ({placeholders}) '
                + self._conflict_clause(target_table, columns)
            )

            # Use a savepoint so a single INSERT failure (e.g. unique constraint
            # on a non-PK field) does not abort the whole table transaction.
            cursor.execute("SAVEPOINT sp_insert")
            try:
                cursor.execute(insert_sql, values)
                cursor.execute("RELEASE SAVEPOINT sp_insert")
            except Exception as e:
                cursor.execute("ROLLBACK TO SAVEPOINT sp_insert")
                cursor.close()
                # A unique violation here means this row collides with an already
                # present row on a NON-id column (e.g. admission_no, employee_number,
                # code). Surface it as a duplicate, not a generic error, so it's
                # visible in the summary and to validate_migration.
                if getattr(e, "pgcode", None) == "23505":
                    self.stats['duplicates'].append(
                        f"{target_table}: dropped row {record.get('id')} — "
                        f"unique collision ({str(e).splitlines()[0]})"
                    )
                else:
                    self.stats['errors'].append(f"Error inserting into {target_table}: {e}")
                return False

            cursor.close()
            return True

        except Exception as e:
            self.stats['errors'].append(f"Error inserting into {target_table}: {e}")
            return False

    # def transform_table(
    #     self, fedena_table: str, target_table: Optional[str] = None
    # ) -> bool:
    #     if fedena_table not in FedenaTableMapping.FIELD_MAPPINGS:
    #         print(f"⚠️  No mapping configuration for table: {fedena_table}")
    #         return False

    #     table_config = FedenaTableMapping.FIELD_MAPPINGS[fedena_table]
    #     table_config["source_table"] = fedena_table
    #     target_model = target_table or table_config["target_model"]

    #     print(f"\n🔄 Transforming table: {fedena_table} -> {target_model}")

    #     try:
    #         source_table = table_config.get("source_table", fedena_table)
    #         records = self.parse_fedena_table_data(source_table)

    #         if not records:
    #             print(f"   ℹ️  No data found for table {fedena_table}")
    #             return True

    #         if "filters" in table_config:
    #             original_count = len(records)
    #             for filter_condition in table_config["filters"]:
    #                 if "is_deleted = 0" in filter_condition:
    #                     records = [
    #                         r for r in records if r.get("is_deleted") in (0, "0", None)
    #                     ]
    #             print(f"   📝 Applied filters: {original_count} -> {len(records)} records")

    #         success_count = 0
    #         for record in records:
    #             try:
    #                 transformed_record = self.transform_record(record, table_config)
    #                 if target_model == "core_batchstudent":
    #                     if not transformed_record.get("student_id"):
    #                         print(
    #                             f"   ⚠️  Skipping batch_student record {record.get('id')}: student_id {record.get('student_id')} not found in id_mappings"
    #                         )
    #                         self.stats["errors"].append(
    #                             f"Skipped batch_student record {record.get('id')}: student_id {record.get('student_id')} not found"
    #                         )
    #                         continue
    #                     if not transformed_record.get("batch_id"):
    #                         print(
    #                             f"   ⚠️  Skipping batch_student record {record.get('id')}: batch_id {record.get('batch_id')} not found in id_mappings"
    #                         )
    #                         self.stats["errors"].append(
    #                             f"Skipped batch_student record {record.get('id')}: batch_id {record.get('batch_id')} not found"
    #                         )
    #                         continue
    #                 if self.insert_transformed_record(
    #                     transformed_record, target_model, table_config
    #                 ):
    #                     success_count += 1
    #                 else:
    #                     print(
    #                         f"   ⚠️  Failed to insert record {record.get('id')} in {fedena_table}"
    #                     )
    #                     self.stats["errors"].append(
    #                         f"Failed to insert record {record.get('id')} in {fedena_table}"
    #                     )
    #             except Exception as e:
    #                 self.stats["errors"].append(
    #                     f"Error transforming record {record.get('id')} in {fedena_table}: {e}"
    #                 )
    #                 print(
    #                     f"   ✗ Error transforming record {record.get('id')} in {fedena_table}: {e}"
    #                 )

    #         print(f"   ✓ Transformed {success_count}/{len(records)} records")
    #         self.stats["records_transformed"] += success_count
    #         self.stats["tables_processed"] += 1

    #         return success_count > 0

    #     except Exception as e:
    #         print(f"   ✗ Transformation failed: {e}")
    #         self.stats["errors"].append(f"Error transforming table {fedena_table}: {e}")
    #         return False

    def validate_foreign_keys(self, record: Dict[str, Any], table_config: Dict) -> bool:
        if table_config["target_model"] == "core_batchstudent":
            # Must validate student_id and batch_id explicitly — the DB FK constraint
            # is deferred (fires at COMMIT, not INSERT) so savepoints won't catch it.
            # Orphaned records (student deleted in source) must be skipped here.
            try:
                cursor = self.connection.cursor()
                for fk_field, ref_table in [("student_id", "core_student"), ("batch_id", "core_batch")]:
                    fk_val = record.get(fk_field)
                    if not fk_val:
                        cursor.close()
                        return False
                    cursor.execute(f'SELECT 1 FROM "{ref_table}" WHERE id = %s', (fk_val,))
                    if not cursor.fetchone():
                        self.stats["errors"].append(
                            f"Skipped batchstudent: {fk_field}={fk_val} not in {ref_table}"
                        )
                        cursor.close()
                        return False
                cursor.close()
                return True
            except Exception as e:
                self.stats["errors"].append(f"FK check error for batchstudent: {e}")
                return False
        try:
            cursor = self.connection.cursor()
            fk_tables = {
                "student_id": "core_student",
                "batch_id": "core_batch",
                "course_id": "core_course",
                "academic_year_id": "core_academicyear",
                "finance_fee_id": "core_financefee",
                "category_id": "core_financetransactioncategory",
                "fee_category_id": "core_feecategory",
                "finance_transaction_id": "core_financetransaction",
                "guardian_id": "core_guardian",
                "privilege_id": "core_privilege",
                # Skip validation for tables that don't exist yet
                # "transaction_receipt_id": "core_transactionreceipt",
                # "fee_account_id": "core_feeaccount",
                # "fee_receipt_template_id": "core_feetemplate",
            }
            for source_field, target_config in table_config["fields"].items():
                target_field = target_config["target"]
                if target_field.endswith("_id") and record.get(target_field):
                    # Skip validation for fields not in fk_tables mapping
                    if target_field not in fk_tables:
                        continue
                    ref_table = fk_tables.get(target_field)
                    cursor.execute(f'SELECT 1 FROM "{ref_table}" WHERE id = %s', (record[target_field],))
                    if not cursor.fetchone():
                        self.stats["errors"].append(f"Foreign key violation: {target_field} = {record[target_field]} not found in {ref_table}")
                        print(f"   ⚠️  Foreign key violation: {target_field} = {record[target_field]} not found in {ref_table}")
                        cursor.close()
                        return False
            cursor.close()
            return True
        except Exception as e:
            self.stats["errors"].append(
                f"Error validating foreign keys for {table_config['target_model']}: {e}"
            )
            print(
                f"   ✗ Error validating foreign keys for {table_config['target_model']}: {e}"
            )
            return False

    def _topological_order(self, table_names: List[str]) -> List[str]:
        """Deterministic, foundation-first topological sort.

        A table is emitted only after every dependency it declares (that is also part of
        this run) has been emitted — so parents always precede children. Among the tables
        that are ready at each step, the lowest (TABLE_PRIORITY, name) goes first, which
        pulls global/system and reference tables to the front and makes the order stable
        across runs (the old set-based version was non-deterministic).
        """
        priority = FedenaTableMapping.TABLE_PRIORITY
        in_run = set(table_names)
        pending = list(in_run)
        done: List[str] = []
        done_set: set = set()

        def sort_key(t: str):
            return (priority.get(t, 5), t)

        while pending:
            ready = []
            for t in pending:
                deps = set(FedenaTableMapping.FIELD_MAPPINGS.get(t, {}).get("dependencies", []))
                # Only deps that are part of THIS run can (and must) be satisfied here.
                if (deps & in_run) <= done_set:
                    ready.append(t)

            if not ready:
                # Circular or unresolvable deps — emit the remainder deterministically so
                # the run still proceeds (ON CONFLICT/FK-skip keep it safe).
                leftover = sorted(pending, key=sort_key)
                print(f"   ⚠️  Unresolved dependency cycle among: {leftover}")
                done.extend(leftover)
                break

            for t in sorted(ready, key=sort_key):
                done.append(t)
                done_set.add(t)
                pending.remove(t)

        return done

    def get_dependency_order(self) -> List[str]:
        """All mapped tables in foundation-first dependency order."""
        return self._topological_order(list(FedenaTableMapping.FIELD_MAPPINGS.keys()))

    def get_table_with_dependencies(self, table_name: str) -> List[str]:
        """A single table plus all its (transitive) dependencies, in proper order."""
        collected = set()

        def collect(table: str):
            for dep in FedenaTableMapping.FIELD_MAPPINGS.get(table, {}).get("dependencies", []):
                if dep not in collected:
                    collected.add(dep)
                    collect(dep)

        collect(table_name)
        collected.add(table_name)
        return self._topological_order(list(collected))

    def transform_all(self, specific_table: Optional[str] = None,
                      include_dependencies: bool = True) -> bool:
        """Transform all tables, or one table.

        include_dependencies=True (default): `specific_table` is run together with its
        dependencies, in order. Set it False to run EXACTLY that one table (used by the
        per-table runner, where dependencies were already migrated in earlier steps).
        """
        if not self.connect_to_database():
            return False

        try:
            if specific_table:
                if specific_table not in FedenaTableMapping.FIELD_MAPPINGS:
                    print(f"✗ Table '{specific_table}' not found in mapping configuration")
                    return False
                if include_dependencies:
                    tables_to_process = self.get_table_with_dependencies(specific_table)
                else:
                    tables_to_process = [specific_table]
            else:
                tables_to_process = self.get_dependency_order()

            print(f"\n🚀 Starting transformation of {len(tables_to_process)} table(s)...")
            print(f"   Processing order: {' -> '.join(tables_to_process)}")

            success_count = 0
            table_results = []  # (table, ok) — per-table outcome for the summary
            for table in tables_to_process:
                ok = self.transform_table(table)
                table_results.append((table, ok))
                if ok:
                    success_count += 1

            # Print summary
            print(f"\n📊 Transformation Summary:")
            print(f"   Tables processed: {self.stats['tables_processed']}")
            print(f"   Records transformed: {self.stats['records_transformed']}")
            print(f"   Successful tables: {success_count}/{len(tables_to_process)}")

            # Per-table breakdown so it's clear exactly which tables failed.
            failed_tables = [t for t, ok in table_results if not ok]
            if failed_tables:
                print(f"   Tables with no rows committed ({len(failed_tables)}): {', '.join(failed_tables)}")

            if self.stats.get('duplicates'):
                print(f"   Duplicates dropped (natural-key collisions): {len(self.stats['duplicates'])}")
                for dup in self.stats['duplicates'][:5]:
                    print(f"     - {dup}")
                if len(self.stats['duplicates']) > 5:
                    print(f"     ... and {len(self.stats['duplicates']) - 5} more")

            if self.stats.get('skipped'):
                print(f"   Orphan rows skipped (missing parent FK): {len(self.stats['skipped'])} table(s)")
                for sk in self.stats['skipped'][:5]:
                    print(f"     - {sk}")
                if len(self.stats['skipped']) > 5:
                    print(f"     ... and {len(self.stats['skipped']) - 5} more")

            if self.stats.get('schema_mismatches'):
                print(f"   ⚠️  Schema mismatches (mapped columns not on model, dropped): {len(self.stats['schema_mismatches'])}")
                for sm in self.stats['schema_mismatches']:
                    print(f"     - {sm}")

            if self.stats.get('warnings'):
                print(f"   Warnings: {len(self.stats['warnings'])}")

            if self.stats['errors']:
                print(f"   Errors: {len(self.stats['errors'])}")
                for error in self.stats['errors'][:5]:
                    print(f"     - {error}")
                if len(self.stats['errors']) > 5:
                    print(f"     ... and {len(self.stats['errors']) - 5} more errors")

            return success_count == len(tables_to_process)

        except Exception as e:
            print(f"✗ Transformation failed: {e}")
            return False

        finally:
            if self.connection:
                self.connection.close()
                print("🔐 Database connection closed")


def get_db_config_from_env() -> Dict[str, str]:
    """Get database configuration from environment variables."""
    return {
        'host': os.getenv('DATABASE_HOST', 'localhost'),
        'port': int(os.getenv('DATABASE_PORT', 5433)),
        'database': os.getenv('DATABASE_NAME', 'pinewood_db'),
        'user': os.getenv('DATABASE_USER', 'pinewood'),
        'password': os.getenv('DATABASE_PASSWORD', '')
    }


def main():
    """Main entry point for the transformation script."""
    parser = argparse.ArgumentParser(description='Transform Fedena data to Pinewood format')
    parser.add_argument('--dry-run', action='store_true', help='Show what would be transformed without actually doing it')
    parser.add_argument('--table', help='Transform the specified table together with its dependencies')
    parser.add_argument('--only', help='Transform EXACTLY this one table (skip dependency expansion). '
                                       'Use after its dependencies are already migrated, e.g. to retry a single table.')
    parser.add_argument('--list-order', action='store_true',
                        help='Print the foundation-first table order (one per line) and exit. '
                             'Useful for driving a per-table run loop. Does not touch the database.')
    parser.add_argument('--sql-file', help='Path to the SQL dump file (optional if using --mysql)')
    parser.add_argument('--tenant-id', help='Target tenant ID for multi-tenant data (required unless --list-order)')
    parser.add_argument('--mysql', action='store_true', help='Connect directly to MySQL database instead of using SQL file')
    parser.add_argument('--mysql-host', default='localhost', help='MySQL host (default: localhost)')
    parser.add_argument('--mysql-port', type=int, default=3306, help='MySQL port (default: 3306)')
    parser.add_argument('--mysql-user', default='pinewood', help='MySQL username (default: pinewood)')
    parser.add_argument('--mysql-password', default='fedenapw', help='MySQL password (default: fedenapw)')
    parser.add_argument('--mysql-database', default='fedena_school_77_production', help='MySQL database name')
    parser.add_argument('--max-error-rate', type=float, default=0.05,
                        help='Max tolerable per-table error rate before rolling back (0.0–1.0, default: 0.05)')

    args = parser.parse_args()

    # --list-order just prints the dependency order (no DB, no tenant needed). Keep
    # stdout clean (table names only) so a shell loop can consume it directly.
    if args.list_order:
        probe = FedenaDataTransformer(None, {}, tenant_id="", mysql_config=None, dry_run=True)
        for table in probe.get_dependency_order():
            print(table)
        sys.exit(0)

    if not args.tenant_id:
        parser.error("--tenant-id is required (unless --list-order)")

    # Load environment variables
    try:
        from dotenv import load_dotenv
        load_dotenv()
    except ImportError:
        print("⚠️  python-dotenv not installed, using system environment variables")

    # Get database configuration
    db_config = get_db_config_from_env()

    # Setup MySQL configuration if using direct connection
    mysql_config = None
    sql_file = None

    if args.mysql:
        mysql_config = {
            'host': args.mysql_host,
            'port': args.mysql_port,
            'user': args.mysql_user,
            'password': args.mysql_password,
            'database': args.mysql_database
        }
    else:
        # Determine SQL file path
        script_dir = Path(__file__).parent
        if args.sql_file:
            sql_file = script_dir / args.sql_file
        else:
            sql_file = script_dir / 'fedena_pinewood.sql'

        if not sql_file.exists():
            print(f"✗ SQL file not found: {sql_file}")
            sys.exit(1)

    print("🔄 Fedena to Pinewood Data Transformation")
    print("=" * 45)

    if args.mysql:
        print(f"MySQL Source: {mysql_config['user']}@{mysql_config['host']}:{mysql_config['port']}/{mysql_config['database']}")
    else:
        print(f"SQL File: {sql_file}")

    print(f"PostgreSQL Target: {db_config['user']}@{db_config['host']}:{db_config['port']}/{db_config['database']}")
    print(f"Tenant ID: {args.tenant_id}")
    print(f"Mode: {'DRY RUN' if args.dry_run else 'LIVE TRANSFORMATION'}")

    if args.table:
        print(f"Target Table (with dependencies): {args.table}")
    if args.only:
        print(f"Target Table (only, no dependencies): {args.only}")

    print()

    # Create transformer and run transformation
    transformer = FedenaDataTransformer(sql_file, db_config, args.tenant_id, mysql_config, dry_run=args.dry_run, max_error_rate=args.max_error_rate)

    try:
        # Connect to MySQL if specified
        if args.mysql:
            if not transformer.connect_to_mysql():
                print("✗ Failed to connect to MySQL database")
                sys.exit(1)

        if args.only:
            # Run exactly one table, no dependency expansion (per-table runner).
            success = transformer.transform_all(specific_table=args.only, include_dependencies=False)
        else:
            success = transformer.transform_all(specific_table=args.table)
        sys.exit(0 if success else 1)
    except KeyboardInterrupt:
        print("\n🛑 Transformation interrupted by user")
        sys.exit(1)
    except Exception as e:
        print(f"\n💥 Unexpected error: {e}")
        sys.exit(1)


if __name__ == '__main__':
    main()

"""
Grading API - Dynamic grade retrieval for marks entry.

Provides endpoints to get available grade values based on subject/assessment configuration.
"""

from rest_framework.decorators import api_view
from rest_framework.response import Response
from rest_framework import status
from django.shortcuts import get_object_or_404

from core.models import Subject, SubjectSkillSet, GradingScale, GradeValue


@api_view(['GET'])
def get_subject_grades(request, subject_id):
    tenant = request.tenant
    subject = get_object_or_404(Subject, id=subject_id, tenant=tenant, is_deleted=False)

    grading_scale = subject.get_grading_scale()

    if not grading_scale:
        return Response({
            'error': 'No grading scale configured for this subject'
        }, status=status.HTTP_404_NOT_FOUND)

    grade_values = subject.get_available_grades()

    response_data = {
        'subject_id': str(subject.id),
        'subject_name': subject.name,
        'subject_code': subject.code,
        'grading_scale': {
            'id': str(grading_scale.id),
            'name': grading_scale.name,
            'type': grading_scale.scale_type,
            'type_display': grading_scale.get_scale_type_display()
        },
        'grades': [
            {
                'id': str(grade.id),
                'name': grade.name,
                'code': grade.code,
                'min_percentage': float(grade.min_percentage) if grade.min_percentage else None,
                'max_percentage': float(grade.max_percentage) if grade.max_percentage else None,
                'gpa_value': float(grade.gpa_value) if grade.gpa_value else None,
                'is_passing': grade.is_passing,
                'color': grade.color_code
            }
            for grade in grade_values
        ]
    }

    return Response(response_data)


@api_view(['GET'])
def get_assessment_grades(request, assessment_id, assessment_type):
    """
    Get available grade values for a specific assessment.

    Parameters:
    - assessment_id: UUID of the assessment (Exam, ActivityAssessment, etc.)
    - assessment_type: Type of assessment ('exam', 'activity', 'skill')

    This endpoint intelligently determines the grading scale based on
    the assessment configuration and subject settings.
    """
    tenant = request.tenant

    grading_scale = None

    if assessment_type == 'exam':
        from core.models import Exam
        assessment = get_object_or_404(Exam, id=assessment_id, tenant=tenant)
        # Exam-level override takes priority over the subject's scale.
        grading_scale = assessment.get_grading_scale()

    elif assessment_type == 'activity':
        from core.models import ActivityAssessment
        assessment = get_object_or_404(ActivityAssessment, id=assessment_id, tenant=tenant)
        subject_skill_set = assessment.subject_skill_set

        # Check for custom grading scale on SubjectSkillSet
        if subject_skill_set.grading_scale:
            grading_scale = subject_skill_set.grading_scale
        else:
            # Fall back to subject's grading scale
            subject = subject_skill_set.subject
            grading_scale = subject.get_grading_scale()

    elif assessment_type == 'skill':
        from core.models import SkillsAssessment
        assessment = get_object_or_404(SkillsAssessment, id=assessment_id, tenant=tenant)
        # For skills, use the skill-specific grading scale
        grading_scale = GradingScale.objects.filter(
            tenant=tenant,
            code='SKILL_LEVELS',
            is_active=True
        ).first()

    else:
        return Response({
            'error': f'Invalid assessment type: {assessment_type}'
        }, status=status.HTTP_400_BAD_REQUEST)

    if not grading_scale:
        return Response({
            'error': 'No grading scale configured for this assessment'
        }, status=status.HTTP_404_NOT_FOUND)

    grade_values = grading_scale.grade_values.filter(
        tenant=tenant
    ).order_by('display_order')

    response_data = {
        'assessment_id': str(assessment_id),
        'assessment_type': assessment_type,
        'grading_scale': {
            'id': str(grading_scale.id),
            'name': grading_scale.name,
            'type': grading_scale.scale_type
        },
        'grades': [
            {
                'id': str(grade.id),
                'name': grade.name,
                'code': grade.code,
                'min_percentage': float(grade.min_percentage) if grade.min_percentage else None,
                'max_percentage': float(grade.max_percentage) if grade.max_percentage else None,
                'is_passing': grade.is_passing,
                'color': grade.color_code
            }
            for grade in grade_values
        ]
    }

    return Response(response_data)


@api_view(['GET'])
def get_batch_grading_scales(request, batch_id):
    """
    Get all grading scales used by subjects in a batch.

    Useful for batch-level grade entry where different subjects
    may use different grading scales.

    Returns a mapping of subject_id -> grading_scale info
    """
    tenant = request.tenant

    from core.models import Batch
    batch = get_object_or_404(Batch, id=batch_id, tenant=tenant, is_deleted=False)

    subjects = Subject.objects.filter(
        batch=batch,
        tenant=tenant,
        is_deleted=False
    ).select_related('grading_scale')

    subjects_grading = []
    for subject in subjects:
        grading_scale = subject.get_grading_scale()
        grade_values = subject.get_available_grades()

        subjects_grading.append({
            'subject_id': str(subject.id),
            'subject_name': subject.name,
            'subject_code': subject.code,
            'grading_scale': {
                'id': str(grading_scale.id) if grading_scale else None,
                'name': grading_scale.name if grading_scale else None,
                'type': grading_scale.scale_type if grading_scale else None
            } if grading_scale else None,
            'grades': [
                {
                    'id': str(grade.id),
                    'name': grade.name,
                    'code': grade.code,
                    'is_passing': grade.is_passing,
                    'color': grade.color_code
                }
                for grade in grade_values
            ]
        })

    return Response({
        'batch_id': str(batch.id),
        'batch_name': batch.name,
        'subjects': subjects_grading
    })


@api_view(['GET'])
def get_available_grading_scales(request):
    """
    Get all available grading scales for the tenant.

    Used in admin/configuration interfaces to allow
    selecting grading scales for subjects.
    """
    tenant = request.tenant

    grading_scales = GradingScale.objects.filter(
        tenant=tenant,
        is_active=True
    ).prefetch_related('grade_values')

    scales_data = []
    for scale in grading_scales:
        scales_data.append({
            'id': str(scale.id),
            'name': scale.name,
            'code': scale.code,
            'type': scale.scale_type,
            'type_display': scale.get_scale_type_display(),
            'description': scale.description,
            'is_default': scale.is_default,
            'grade_count': scale.grade_values.count(),
            'grades': [
                {
                    'id': str(grade.id),
                    'name': grade.name,
                    'code': grade.code
                }
                for grade in scale.grade_values.all()[:5]  # Preview first 5
            ]
        })

    return Response({
        'grading_scales': scales_data
    })
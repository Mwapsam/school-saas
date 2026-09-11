import logging
from typing import Dict, Any, List
from django.shortcuts import render, redirect, get_object_or_404
from django.http import JsonResponse, Http404
from django.views.generic import TemplateView, View
from django.db import transaction
from django.contrib import messages
from django.urls import reverse
from django.db.models import Q, Prefetch

from core.models import (
    ExtendedAdmissionApplication, 
    Student, 
    Batch, 
    BatchStudent,
    Course,
    AcademicYear
)
from core.services.extended_admission_service import ExtendedAdmissionService
from core.services.exceptions import ValidationException, ServiceException

logger = logging.getLogger(__name__)


class BatchAssignmentListView(TemplateView):
    template_name = 'core/admission/batch_assignment_list.html'
    
    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        
        school = getattr(self.request, 'tenant', None)
        if not school:
            raise Http404("School not found")
        
        # Get approved applications that haven't been converted to students yet
        approved_applications = ExtendedAdmissionApplication.objects.filter(
            tenant=school,
            status='approved'
        ).select_related(
            'academic_year', 'course_applied', 'student_category', 'country'
        ).order_by('-application_date')
        
        # Get admitted applications (students created but may not have batch assignment)
        admitted_applications = ExtendedAdmissionApplication.objects.filter(
            tenant=school,
            status='admitted'
        ).select_related(
            'academic_year', 'course_applied', 'student_category', 'country'
        ).order_by('-application_date')
        
        applications_for_assignment = []
        
        # Add all approved applications
        for app in approved_applications:
            existing_student = Student.objects.filter(
                tenant=school,
                first_name__iexact=app.first_name,
                last_name__iexact=app.last_name,
                date_of_birth=app.date_of_birth
            ).first()
            
            # If student exists, check if they have batch assignment
            if existing_student:
                has_batch_assignment = BatchStudent.objects.filter(
                    tenant=school,
                    student=existing_student,
                    is_active=True
                ).exists()
                
                # Only add if student doesn't have batch assignment
                if not has_batch_assignment:
                    applications_for_assignment.append(app)
            else:
                # No student exists yet, so add application
                applications_for_assignment.append(app)
        
        # Add admitted applications where students don't have batch assignments
        for app in admitted_applications:
            existing_student = Student.objects.filter(
                tenant=school,
                first_name__iexact=app.first_name,
                last_name__iexact=app.last_name,
                date_of_birth=app.date_of_birth
            ).first()
            
            if existing_student:
                # Check if student has any active batch assignments
                has_batch_assignment = BatchStudent.objects.filter(
                    tenant=school,
                    student=existing_student,
                    is_active=True
                ).exists()
                
                if not has_batch_assignment:
                    applications_for_assignment.append(app)
        
        context['applications'] = applications_for_assignment
        context['school'] = school

        academic_years = AcademicYear.objects.filter(
            tenant=school,
            is_active=True
        ).order_by('-start_date')
        context['academic_years'] = academic_years

        courses_with_batches = Course.objects.filter(
            tenant=school,
            is_deleted=False
        ).prefetch_related(
            Prefetch(
                'batches',
                queryset=Batch.objects.filter(
                    is_deleted=False,
                    is_active=True
                ).order_by('name')
            )
        ).order_by('course_name')
        context['courses_with_batches'] = courses_with_batches

        # Calculate statistics including both approved and admitted applications
        total_approved = ExtendedAdmissionApplication.objects.filter(
            tenant=school,
            status='approved'
        ).count()

        total_admitted = ExtendedAdmissionApplication.objects.filter(
            tenant=school,
            status='admitted'
        ).count()

        total_eligible = total_approved + total_admitted
        total_assigned = total_eligible - len(applications_for_assignment)

        context['stats'] = {
            'total_approved': total_eligible,  # Show total eligible (approved + admitted)
            'pending_assignment': len(applications_for_assignment),
            'already_assigned': total_assigned
        }

        context['back_url'] = self.request.GET.get('back', reverse('core:admission_manage'))
        context['crumbs'] = [
            {'label': 'Admission', 'url': reverse('core:admission_manage')},
            {'label': 'Batch Assignments'},
        ]

        return context


class BatchAssignmentView(View):
    def post(self, request, *args, **kwargs):
        school = getattr(request, 'tenant', None)
        if not school:
            return JsonResponse({'error': 'School not found'}, status=400)
        
        try:
            action = request.POST.get('action')
            
            if action == 'assign_single':
                return self._assign_single_application(request, school)
            elif action == 'assign_bulk':
                return self._assign_bulk_applications(request, school)
            else:
                return JsonResponse({'error': 'Invalid action'}, status=400)
                
        except Exception as e:
            logger.error(f"Error in batch assignment: {str(e)}")
            return JsonResponse({'error': str(e)}, status=500)
    
    def _assign_single_application(self, request, school):
        application_id = request.POST.get('application_id')
        batch_id = request.POST.get('batch_id')
        roll_number = request.POST.get('roll_number', '')
        
        if not application_id or not batch_id:
            return JsonResponse({'error': 'Application ID and Batch ID are required'}, status=400)
        
        try:
            with transaction.atomic():
                application = get_object_or_404(
                    ExtendedAdmissionApplication,
                    id=application_id,
                    tenant=school,
                    status__in=['approved', 'admitted']
                )
                
                batch = get_object_or_404(
                    Batch,
                    id=batch_id,
                    tenant=school,
                    is_deleted=False,
                    is_active=True
                )
                
                # If application is already admitted, find existing student
                if application.status == 'admitted':
                    student = Student.objects.filter(
                        tenant=school,
                        first_name__iexact=application.first_name,
                        last_name__iexact=application.last_name,
                        date_of_birth=application.date_of_birth
                    ).first()
                    
                    if not student:
                        return JsonResponse({'error': 'Student record not found for admitted application'}, status=404)
                        
                    # Check if student already has a batch assignment
                    existing_assignment = BatchStudent.objects.filter(
                        tenant=school,
                        student=student,
                        is_active=True
                    ).first()
                    
                    if existing_assignment:
                        return JsonResponse({'error': f'Student is already assigned to batch: {existing_assignment.batch.name}'}, status=400)
                else:
                    # Create new student for approved application
                    student = self._create_student_from_application(application, school)
                    application.status = 'admitted' 
                    application.save()
                
                batch_student = BatchStudent.objects.create(
                    tenant=school,
                    batch=batch,
                    student=student,
                    roll_number=roll_number if roll_number else None,
                    is_active=True
                )
                
                return JsonResponse({
                    'success': True,
                    'message': f'Successfully assigned {student.full_name} to {batch.name}',
                    'student_id': student.id,
                    'batch_student_id': batch_student.id
                })
                
        except Exception as e:
            logger.error(f"Error assigning single application: {str(e)}")
            return JsonResponse({'error': str(e)}, status=500)
    
    def _assign_bulk_applications(self, request, school):
        assignments = request.POST.get('assignments')  
        
        if not assignments:
            return JsonResponse({'error': 'No assignments provided'}, status=400)
        
        try:
            import json
            assignments_data = json.loads(assignments)
            
            results = {
                'successful': 0,
                'failed': 0,
                'errors': []
            }
            
            with transaction.atomic():
                for assignment in assignments_data:
                    try:
                        application_id = assignment.get('application_id')
                        batch_id = assignment.get('batch_id')
                        roll_number = assignment.get('roll_number', '')
                        
                        if not application_id or not batch_id:
                            results['failed'] += 1
                            results['errors'].append(f"Missing data for assignment")
                            continue
                        
                        application = ExtendedAdmissionApplication.objects.get(
                            id=application_id,
                            tenant=school,
                            status__in=['approved', 'admitted']
                        )
                        
                        batch = Batch.objects.get(
                            id=batch_id,
                            tenant=school,
                            is_deleted=False,
                            is_active=True
                        )
                        
                        # Handle admitted applications differently
                        if application.status == 'admitted':
                            student = Student.objects.filter(
                                tenant=school,
                                first_name__iexact=application.first_name,
                                last_name__iexact=application.last_name,
                                date_of_birth=application.date_of_birth
                            ).first()
                            
                            if not student:
                                results['failed'] += 1
                                results['errors'].append(f"Student record not found for application {application.application_number}")
                                continue
                                
                            # Check if student already has a batch assignment
                            existing_assignment = BatchStudent.objects.filter(
                                tenant=school,
                                student=student,
                                is_active=True
                            ).first()
                            
                            if existing_assignment:
                                results['failed'] += 1
                                results['errors'].append(f"Student {student.first_name} {student.last_name} is already assigned to batch: {existing_assignment.batch.name}")
                                continue
                        else:
                            # Create new student for approved application
                            student = self._create_student_from_application(application, school)
                            application.status = 'admitted'
                            application.save()
                        
                        BatchStudent.objects.create(
                            tenant=school,
                            batch=batch,
                            student=student,
                            roll_number=roll_number if roll_number else None,
                            is_active=True
                        )
                        
                        results['successful'] += 1
                        
                    except Exception as e:
                        results['failed'] += 1
                        results['errors'].append(f"Error processing application {application_id}: {str(e)}")
                        logger.error(f"Bulk assignment error: {str(e)}")
            
            return JsonResponse({
                'success': True,
                'message': f'Bulk assignment completed: {results["successful"]} successful, {results["failed"]} failed',
                'results': results
            })
            
        except Exception as e:
            logger.error(f"Error in bulk assignment: {str(e)}")
            return JsonResponse({'error': str(e)}, status=500)
    
    def _create_student_from_application(self, application: ExtendedAdmissionApplication, school) -> Student:
        admission_number = self._generate_admission_number(school)
        
        student = Student.objects.create(
            tenant=school,
            
            admission_number=admission_number,
            admission_date=application.application_date.date(),
            first_name=application.first_name,
            middle_name=application.middle_name or '',
            last_name=application.last_name,
            date_of_birth=application.date_of_birth,
            gender=application.gender,
            nationality=application.nationality or '',
            religion=application.religion or '',
            birth_place=application.birth_place or '',
            mother_tongue=application.mother_tongue or '',
            
            email=application.email or '',
            phone=application.phone or '',
            mobile=application.mobile or '',
            address=application.address or '',
            address_line1=application.address_line1 or '',
            address_line2=application.address_line2 or '',
            city=application.city or '',
            country=application.country,
            
            guardian1_first_name=application.guardian1_first_name or '',
            guardian1_last_name=application.guardian1_last_name or '',
            guardian1_relation=application.guardian1_relation or '',
            guardian1_occupation=application.guardian1_occupation or '',
            guardian1_office_address_line1=application.guardian1_office_address_line1 or '',
            guardian1_office_city=application.guardian1_office_city or '',
            guardian1_office_phone1=application.guardian1_office_phone1 or '',
            guardian1_mobile=application.guardian1_mobile or '',
            guardian1_email=application.guardian1_email or '',
            
            guardian2_first_name=application.guardian2_first_name or '',
            guardian2_last_name=application.guardian2_last_name or '',
            guardian2_relation=application.guardian2_relation or '',
            guardian2_occupation=application.guardian2_occupation or '',
            guardian2_office_address_line1=application.guardian2_office_address_line1 or '',
            guardian2_office_city=application.guardian2_office_city or '',
            guardian2_office_phone1=application.guardian2_office_phone1 or '',
            guardian2_mobile=application.guardian2_mobile or '',
            guardian2_email=application.guardian2_email or '',
            
            previous_school_name=application.previous_school_name or '',
            previous_school_address=application.previous_school_address or '',
            previous_school_phone=application.previous_school_phone or '',
            previous_school_email=application.previous_school_email or '',
            
            has_medical_problems=application.has_medical_problems or False,
            recent_hospitalization=application.recent_hospitalization or False,
            has_allergies=application.has_allergies or False,
            medical_details=application.medical_details or '',
            
            student_category=application.student_category,
            
            religious_observances=application.religious_observances or '',
            background_information=application.background_information or '',
            
            is_active=True,
            is_deleted=False,
            status='active'
        )
        
        logger.info(f"Created student {student.admission_number} from application {application.application_number}")
        
        return student
    
    def _generate_admission_number(self, school) -> str:
        from datetime import datetime
        import random
        import string
        
        year = datetime.now().year
        
        while True:
            random_part = ''.join(random.choices(string.digits, k=4))
            admission_number = f"ADM-{year}-{random_part}"
            
            if not Student.objects.filter(
                tenant=school,
                admission_number=admission_number
            ).exists():
                return admission_number


class BatchAssignmentDetailView(TemplateView):
    template_name = 'core/admission/batch_assignment_detail.html'
    
    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        
        application_id = kwargs.get('application_id')
        school = getattr(self.request, 'tenant', None)
        
        if not school:
            raise Http404("School not found")
        
        application = get_object_or_404(
            ExtendedAdmissionApplication,
            id=application_id,
            tenant=school,
            status__in=['approved', 'admitted']
        )
        
        context['application'] = application
        context['school'] = school

        if application.course_applied:
            available_batches = Batch.objects.filter(
                tenant=school,
                course=application.course_applied,
                is_deleted=False,
                is_active=True
            ).order_by('name')
            context['available_batches'] = available_batches

        context['back_url'] = self.request.GET.get('back', reverse('core:batch_assignment_list'))
        context['crumbs'] = [
            {'label': 'Admission', 'url': reverse('core:admission_manage')},
            {'label': 'Batch Assignments', 'url': reverse('core:batch_assignment_list')},
            {'label': 'Assign Batch'},
        ]

        return context
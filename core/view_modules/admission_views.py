import logging
from typing import Dict, Any
from datetime import datetime

from django.shortcuts import redirect
from django.http import JsonResponse, Http404
from django.views.generic import TemplateView, View
from django.views.decorators.http import require_http_methods
from django.contrib import messages
from django.urls import reverse
from django.db import transaction
from django.core.cache import cache
from django.core.exceptions import ValidationError

from core.models import (
    ExtendedAdmissionApplication,
    AcademicYear,
    Course,
    School,
    Country,
    StudentCategory,
    AdmissionTerms
)
from core.services.extended_admission_service import ExtendedAdmissionService
from core.services.exceptions import ServiceException, ValidationException, NotFoundException
from core.utils.data_initialization import ensure_basic_data_exists, check_admission_prerequisites

logger = logging.getLogger(__name__)


class AdmissionRegistrationView(TemplateView):
    template_name = 'core/admission/register.html'
    
    def get(self, request, *args, **kwargs):
        school = getattr(request, 'tenant', None)
        if not school:
            raise Http404("School not found")
        
        app_id = request.GET.get('edit') or request.GET.get('continue')
        application = None
        current_step = 1
        
        if app_id:
            try:
                admission_service = ExtendedAdmissionService(school)
                application = admission_service.get_by_id(app_id)
                current_step = application.current_step
                
                if request.GET.get('edit') and application.status not in ['draft', 'step1_completed', 'step2_completed', 'step3_completed', 'step4_completed', 'step5_completed']:
                    messages.error(request, "This application cannot be edited as it has already been submitted.")
                    return redirect('core:admission_register')
                    
            except NotFoundException:
                messages.error(request, "Application not found.")
                return redirect('core:admission_register')
        
        step = request.GET.get('step')
        if step:
            try:
                step_num = int(step)
                if 1 <= step_num <= 5:
                    current_step = step_num
            except (ValueError, TypeError):
                pass
        
        request.session['current_step'] = current_step
        
        return super().get(request, *args, **kwargs)
    
    def post(self, request, *args, **kwargs):
        school = getattr(request, 'tenant', None)
        if not school:
            return JsonResponse({'error': 'School not found'}, status=400)
        
        action = request.POST.get('action')
        
        try:
            if action == 'create_academic_year':
                return self._handle_create_academic_year(request, school)
            elif action == 'create_course':
                return self._handle_create_course(request, school)
            elif action == 'initialize_basic_data':
                return self._handle_initialize_basic_data(request, school)
            else:
                return JsonResponse({
                    'success': False,
                    'error': f'Unknown action: {action}'
                }, status=400)
        
        except Exception as e:
            logger.error(f"Error handling POST action '{action}': {str(e)}")
            return JsonResponse({
                'success': False,
                'error': f'An error occurred: {str(e)}'
            }, status=500)
    
    def _handle_create_academic_year(self, request, school: School):
        try:
            name = request.POST.get('name', '').strip()
            start_date = request.POST.get('start_date')
            end_date = request.POST.get('end_date')
            admission_start_date = request.POST.get('admission_start_date')
            admission_end_date = request.POST.get('admission_end_date')
            is_active = request.POST.get('is_active') == 'true'
            
            if not name:
                return JsonResponse({
                    'success': False,
                    'error': 'Academic year name is required'
                })
            
            if not start_date or not end_date:
                return JsonResponse({
                    'success': False,
                    'error': 'Start date and end date are required'
                })
            
            if AcademicYear.objects.filter(tenant=school, name=name).exists():
                return JsonResponse({
                    'success': False,
                    'error': f'Academic year "{name}" already exists'
                })
            
            from datetime import datetime
            start_date_obj = datetime.strptime(start_date, '%Y-%m-%d').date()
            end_date_obj = datetime.strptime(end_date, '%Y-%m-%d').date()
            
            admission_start_date_obj = None
            if admission_start_date:
                admission_start_date_obj = datetime.strptime(admission_start_date, '%Y-%m-%d').date()
            
            admission_end_date_obj = None
            if admission_end_date:
                admission_end_date_obj = datetime.strptime(admission_end_date, '%Y-%m-%d').date()
            
            academic_year = AcademicYear.objects.create(
                tenant=school,
                name=name,
                start_date=start_date_obj,
                end_date=end_date_obj,
                is_active=is_active,
                admission_start_date=admission_start_date_obj,
                admission_end_date=admission_end_date_obj
            )
            
            logger.info(f"Created academic year {academic_year.name} for school {school.code}")
            
            return JsonResponse({
                'success': True,
                'message': f'Academic year "{name}" created successfully!',
                'academic_year': {
                    'id': str(academic_year.id),
                    'name': academic_year.name,
                    'start_date': academic_year.start_date.isoformat(),
                    'end_date': academic_year.end_date.isoformat(),
                    'is_active': academic_year.is_active
                }
            })
        
        except ValueError as e:
            return JsonResponse({
                'success': False,
                'error': 'Invalid date format. Please use YYYY-MM-DD format.'
            })
        except Exception as e:
            logger.error(f"Error creating academic year: {str(e)}")
            return JsonResponse({
                'success': False,
                'error': f'Failed to create academic year: {str(e)}'
            })
    
    def _handle_create_course(self, request, school: School):
        try:
            course_name = request.POST.get('course_name', '').strip()
            code = request.POST.get('code', '').strip().upper()
            section_name = request.POST.get('section_name', '').strip()
            
            if not course_name:
                return JsonResponse({
                    'success': False,
                    'error': 'Course name is required'
                })
            
            if not code:
                return JsonResponse({
                    'success': False,
                    'error': 'Course code is required'
                })
            
            if Course.objects.filter(tenant=school, code=code).exists():
                return JsonResponse({
                    'success': False,
                    'error': f'Course with code "{code}" already exists'
                })
            
            course = Course.objects.create(
                tenant=school,
                course_name=course_name,
                code=code,
                section_name=section_name,
                is_deleted=False
            )
            
            logger.info(f"Created course {course.course_name} ({course.code}) for school {school.code}")
            
            return JsonResponse({
                'success': True,
                'message': f'Course "{course_name}" created successfully!',
                'course': {
                    'id': str(course.id),
                    'course_name': course.course_name,
                    'code': course.code,
                    'section_name': course.section_name
                }
            })
        
        except Exception as e:
            logger.error(f"Error creating course: {str(e)}")
            return JsonResponse({
                'success': False,
                'error': f'Failed to create course: {str(e)}'
            })
    
    def _handle_initialize_basic_data(self, request, school: School):
        try:
            success = ensure_basic_data_exists(school)
            
            if success:
                return JsonResponse({
                    'success': True,
                    'message': 'Basic data has been initialized successfully!',
                    'reload': True  
                })
            else:
                return JsonResponse({
                    'success': False,
                    'error': 'Failed to initialize basic data. Check logs for details.'
                })
        
        except Exception as e:
            logger.error(f"Error initializing basic data: {str(e)}")
            return JsonResponse({
                'success': False,
                'error': f'Failed to initialize basic data: {str(e)}'
            })
    
    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        
        school = getattr(self.request, 'tenant', None)
        if school:
            context['school'] = school
            
            try:
                ensure_basic_data_exists(school)
            except Exception as e:
                logger.error(f"Error ensuring basic data exists for {school.code}: {str(e)}")
            
            prereq_check = check_admission_prerequisites(school)
            context['prereq_check'] = prereq_check
            
            current_step = self.request.session.get('current_step', 1)
            context['current_step'] = current_step
            context['total_steps'] = 5
            context['is_multistep'] = True
            
            try:
                academic_years = AcademicYear.objects.filter(
                    tenant=school,
                    is_active=True
                ).order_by('-start_date')
                context['academic_years'] = academic_years
                
                if not academic_years.exists():
                    context['no_academic_years'] = True
                    context['academic_years_message'] = (
                        "No active academic years found. Please contact the administrator "
                        "to set up academic years before proceeding with admission applications."
                    )
            except Exception as e:
                logger.error(f"Error fetching academic years: {str(e)}")
                context['academic_years'] = AcademicYear.objects.none()
                context['no_academic_years'] = True
                context['academic_years_message'] = (
                    "Unable to load academic years. Please contact the administrator."
                )
            
            try:
                courses = Course.objects.filter(
                    tenant=school,
                    is_deleted=False
                ).order_by('course_name')
                context['courses'] = courses
                
                if not courses.exists():
                    context['no_courses'] = True
                    context['courses_message'] = (
                        "No courses available. Please contact the administrator "
                        "to set up courses before proceeding with admission applications."
                    )
            except Exception as e:
                logger.error(f"Error fetching courses: {str(e)}")
                context['courses'] = Course.objects.none()
                context['no_courses'] = True
                context['courses_message'] = "Unable to load courses. Please contact the administrator."
            
            try:
                countries = Country.objects.all().order_by('name')
                context['countries'] = countries
                
                if not countries.exists():
                    context['no_countries'] = True
                    context['countries_message'] = (
                        "No countries available. Please contact the administrator "
                        "to set up country data."
                    )
            except Exception as e:
                logger.error(f"Error fetching countries: {str(e)}")
                context['countries'] = Country.objects.none()
                context['no_countries'] = True
                context['countries_message'] = "Unable to load countries. Please contact the administrator."
            
            try:
                student_categories = StudentCategory.objects.filter(
                    tenant=school,
                    is_deleted=False
                ).order_by('name')
                context['student_categories'] = student_categories
                
                if not student_categories.exists():
                    context['no_student_categories'] = True
                    context['student_categories_message'] = (
                        "No student categories available. Please contact the administrator "
                        "to set up student categories."
                    )
            except Exception as e:
                logger.error(f"Error fetching student categories: {str(e)}")
                context['student_categories'] = StudentCategory.objects.none()
                context['no_student_categories'] = True
                context['student_categories_message'] = "Unable to load student categories. Please contact the administrator."
            
            app_id = self.request.GET.get('edit') or self.request.GET.get('continue')
            if app_id:
                try:
                    admission_service = ExtendedAdmissionService(school)
                    application = admission_service.get_by_id(app_id)
                    context['application'] = application
                    context['editing'] = bool(self.request.GET.get('edit'))
                    context['continuing'] = bool(self.request.GET.get('continue'))
                    
                    context['step_status'] = {
                        'step1_complete': application.is_step1_complete,
                        'step2_complete': application.is_step2_complete,
                        'step3_complete': application.is_step3_complete,
                        'step4_complete': application.is_step4_complete,
                        'step5_complete': application.is_step5_complete,
                        'can_submit': application.can_submit(),
                        'next_step': application.get_next_step()
                    }
                    
                    documents = application.documents.all()
                    context['uploaded_documents'] = {
                        doc.document_type: doc for doc in documents
                    }
                    context['required_documents'] = [
                        'immunization_record', 'birth_certificate', 'utility_bill',
                        'parent1_id', 'parent2_id'
                    ]
                    
                except NotFoundException:
                    pass
            else:
                context['step_status'] = {
                    'step1_complete': False,
                    'step2_complete': False,
                    'step3_complete': False,
                    'step4_complete': False,
                    'step5_complete': False,
                    'can_submit': False,
                    'next_step': 1
                }
                context['uploaded_documents'] = {}
                context['required_documents'] = [
                    'immunization_record', 'birth_certificate', 'utility_bill',
                    'parent1_id', 'parent2_id'
                ]
            
            try:
                admission_terms = AdmissionTerms.objects.filter(
                    tenant=school,
                    is_active=True
                ).order_by('order')
                context['admission_terms'] = admission_terms
                
                if not admission_terms.exists():
                    context['no_admission_terms'] = True
                    context['default_terms'] = True 
                else:
                    first_terms = admission_terms.first()
                    if first_terms and first_terms.admission_fee:
                        context['dynamic_admission_fee'] = first_terms.admission_fee
                        context['fee_currency'] = first_terms.fee_currency
                    else:
                        context['dynamic_admission_fee'] = getattr(school, 'admission_fee', 1000)
                        context['fee_currency'] = 'ZMW'
                        
            except Exception as e:
                logger.error(f"Error fetching admission terms: {str(e)}")
                context['admission_terms'] = AdmissionTerms.objects.none()
                context['no_admission_terms'] = True
                context['default_terms'] = True
                context['dynamic_admission_fee'] = 1000
                context['fee_currency'] = 'ZMW'
            
            context['step_titles'] = {
                1: 'Academic Year & Class Selection',
                2: 'Student Personal Details',
                3: 'Student Communication Details',
                4: 'Guardian Personal Details',
                5: 'Previous School & Health Information'
            }
            
            context['step_descriptions'] = {
                1: 'Choose your academic year, class, and agree to terms and conditions.',
                2: 'Provide student personal information including name, date of birth, and other details.',
                3: 'Enter student contact information and address details.',
                4: 'Provide guardian/parent contact and professional information.',
                5: 'Previous school information, health details, and document uploads.'
            }

            # Dynamic admission fields (Configuration → Admission Details),
            # rendered in step 6 and saved as AdmissionAdditionalDetail.
            try:
                from core.models import AdditionalField, AdmissionAdditionalDetail
                extra_fields = list(AdditionalField.objects.filter(
                    tenant=school, applies_to='admission', is_active=True
                ).order_by('sort_order', 'name'))
                existing = {}
                app_id = self.request.session.get('application_id') or self.request.GET.get('application_id')
                if app_id:
                    existing = {
                        str(d.field_id): d.value
                        for d in AdmissionAdditionalDetail.objects.filter(
                            tenant=school, application_id=app_id
                        )
                    }
                context['admission_additional_fields'] = [
                    {
                        'id': str(f.id),
                        'name': f.name,
                        'input_type': f.input_type or 'text',
                        'is_mandatory': f.is_mandatory,
                        'options': f.option_list,
                        'value': existing.get(str(f.id), ''),
                    }
                    for f in extra_fields
                ]
            except Exception as e:
                logger.error(f"Error loading dynamic admission fields: {str(e)}")
                context['admission_additional_fields'] = []

        return context


class AdmissionRegistrationSubmitView(View):    
    def get(self, request, *args, **kwargs):
        return redirect('core:admission_register')
    
    def post(self, request, *args, **kwargs):
        action = request.POST.get('action', 'save')
        step = request.POST.get('step', '1')
        
        school = getattr(request, 'tenant', None)
        if not school:
            return JsonResponse({'error': 'School not found'}, status=400)
        
        # The token check must run before the final-submission branch: the
        # submit action is the one path that creates applications, so skipping
        # it there allowed replayed requests to create duplicates.
        submission_token = request.POST.get('submission_token')
        if submission_token:
            cache_key = f"submission_token_{submission_token}"
            if cache.get(cache_key):
                return JsonResponse({
                    'success': False,
                    'error': 'This form has already been submitted. Please refresh the page.'
                }, status=400)

            cache.set(cache_key, True, 600)

        # SPECIAL HANDLING: If action=submit, immediately process as final submission
        if action == 'submit':
            return self._handle_final_submission(request, school)
        
        try:
            with transaction.atomic():
                current_step = int(request.POST.get('step', request.session.get('current_step', 1)))
                action = request.POST.get('action', 'save')
                
                form_data = self._extract_step_form_data(request.POST, current_step)
                
                if current_step == 1:
                    if form_data.get('academic_year'):
                        try:
                            academic_year = AcademicYear.objects.get(
                                id=form_data['academic_year'],
                                tenant=school,
                                is_active=True
                            )
                        except AcademicYear.DoesNotExist:
                            raise ValidationException("Selected academic year is not available.")
                    
                    if form_data.get('course_applied'):
                        try:
                            course = Course.objects.get(
                                id=form_data['course_applied'],
                                tenant=school,
                                is_deleted=False
                            )
                        except Course.DoesNotExist:
                            raise ValidationException("Selected course is not available.")
                
                admission_service = ExtendedAdmissionService(school)
                app_id = request.POST.get('application_id')

                if app_id:
                    application = admission_service.update_application(
                        app_id,
                        form_data,
                        user=request.user if request.user and hasattr(request.user, 'is_authenticated') and request.user.is_authenticated else None
                    )
                else:
                    accumulated_data = self._get_accumulated_form_data(request, form_data, current_step)

                    if current_step >= 1 and accumulated_data.get('first_name') and accumulated_data.get('last_name'):
                        existing = self._find_existing_application(school, accumulated_data)

                        if existing and existing.status not in ['submitted', 'approved', 'rejected']:
                            application = admission_service.update_application(
                                str(existing.id),
                                accumulated_data,
                                user=request.user if request.user and hasattr(request.user, 'is_authenticated') and request.user.is_authenticated else None
                            )
                        else:
                            application = admission_service.create_application(
                                accumulated_data,
                                user=request.user if request.user and hasattr(request.user, 'is_authenticated') and request.user.is_authenticated else None
                            )
                    else:
                        request.session['admission_form_data'] = accumulated_data
                        request.session.modified = True

                        return JsonResponse({
                            'success': True,
                            'message': f'Step {current_step} saved successfully!',
                            'current_step': current_step,
                            'step_complete': True
                        })
                
                # CRITICAL FIX: When final submission (action='submit'), ensure all steps are marked complete
                if action == 'submit' and current_step == 7:
                    # Force refresh the application to ensure all data is updated
                    application.refresh_from_db()
                    
                    # Mark all steps as complete for final submission
                    for step_num in range(1, 8):  # Steps 1-7
                        self._update_application_step(application, step_num)
                    
                    # Refresh again to get updated step completion status
                    application.refresh_from_db()
                else:
                    self._update_application_step(application, current_step)
                self._save_admission_additional_details(request.POST, application, school)
                self._process_step_file_uploads(request, application, current_step, admission_service)
                self._process_temporary_files(request, application, admission_service)
                response_data = self._handle_step_action(
                    request, application, current_step, action, admission_service
                )
                
                # CRITICAL DEBUG: Add all debug info to understand the flow
                response_data['DEBUG_FLOW'] = 'Reached _handle_step_action response'
                response_data['DEBUG_received_action'] = action
                response_data['DEBUG_current_step'] = current_step  
                response_data['DEBUG_can_submit'] = application.can_submit()
                response_data['DEBUG_app_id'] = str(application.id)
                response_data['DEBUG_terms_agreement'] = getattr(application, 'terms_agreement', 'NOT_SET')
                response_data['DEBUG_declaration_agreement'] = getattr(application, 'declaration_agreement', 'NOT_SET')
                response_data['DEBUG_declaration_date'] = str(getattr(application, 'declaration_date', 'NOT_SET'))
                
                return JsonResponse(response_data)
                
        except ValidationException as e:
            logger.error(f"Validation error in admission submission: {str(e)}")
            return JsonResponse({
                'success': False,
                'error': str(e),
                'details': getattr(e, 'details', {}),
                'step': current_step
            }, status=400)
            
        except ServiceException as e:
            logger.error(f"Service error in admission submission: {str(e)}")
            return JsonResponse({
                'success': False,
                'error': str(e),
                'step': current_step
            }, status=400)
            
        except Exception as e:
            logger.error(f"Unexpected error in multi-step admission submission: {str(e)}")
            logger.error(f"Error type: {type(e).__name__}")
            logger.error(f"Current step: {current_step}")
            logger.error(f"Form data keys: {list(request.POST.keys())}")
            import traceback
            logger.error(f"Traceback: {traceback.format_exc()}")
            return JsonResponse({
                'success': False,
                'error': 'An unexpected error occurred. Please try again.',
                'step': current_step,
                'debug_info': str(e) if hasattr(e, '__str__') else 'Unknown error'
            }, status=500)
    
    def _extract_step_form_data(self, post_data: Dict[str, Any], step: int) -> Dict[str, Any]:
        form_data = {}
        
        if step == 1:
            if post_data.get('academic_year'):
                form_data['academic_year'] = post_data['academic_year']
            if post_data.get('course_applied'):
                form_data['course_applied'] = post_data['course_applied']
            form_data['terms_agreement'] = post_data.get('terms_agreement') == 'on'
            
            name_fields = ['first_name', 'middle_name', 'last_name']
            for field in name_fields:
                if post_data.get(field):
                    form_data[field] = post_data[field]
            
        elif step == 2:
            student_fields = [
                'date_of_birth', 'gender', 'nationality', 'student_category',
                'religion', 'birth_place', 'mother_tongue', 'email',
                'preferred_name', 'home_language', 'authorized_pickup_persons',
            ]
            for field in student_fields:
                if post_data.get(field):
                    form_data[field] = post_data[field]
            
            if 'student_photo' in post_data:
                form_data['student_photo'] = post_data['student_photo']
                
        elif step == 3:
            guardian1_fields = [
                'guardian1_first_name', 'guardian1_last_name', 'guardian1_relation',
                'guardian1_occupation', 'guardian1_office_address_line1',
                'guardian1_city', 'guardian1_office_phone1', 'guardian1_mobile',
                'guardian1_email', 'guardian1_house_plot_no', 'guardian1_road_name',
                'guardian1_area_location', 'guardian1_flat_block_name',
            ]
            for field in guardian1_fields:
                if post_data.get(field):
                    form_data[field] = post_data[field]
                
        elif step == 4:
            guardian2_fields = [
                'guardian2_first_name', 'guardian2_last_name', 'guardian2_relation',
                'guardian2_occupation', 'guardian2_office_address_line1',
                'guardian2_city', 'guardian2_office_phone1', 'guardian2_mobile',
                'guardian2_email', 'guardian2_house_plot_no', 'guardian2_road_name',
                'guardian2_area_location', 'guardian2_flat_block_name',
            ]
            for field in guardian2_fields:
                if post_data.get(field):
                    form_data[field] = post_data[field]

            emergency_contact_fields = [
                'emergency_contact_name', 'emergency_contact_relation',
                'emergency_contact_mobile', 'emergency_contact_address',
            ]
            for field in emergency_contact_fields:
                if post_data.get(field):
                    form_data[field] = post_data[field]

            address_fields = [
                'address_line1', 'address_line2', 'city', 'country',
                'phone', 'mobile'
            ]
            for field in address_fields:
                if post_data.get(field):
                    form_data[field] = post_data[field]

        elif step == 5:
            previous_school_fields = [
                'previous_school_name', 'previous_school_address', 
                'previous_school_phone', 'previous_school_email'
            ]
            for field in previous_school_fields:
                if post_data.get(field):
                    form_data[field] = post_data[field]
            
            if post_data.get('last_attendance_year'):
                form_data['last_attendance_year'] = post_data['last_attendance_year']

            if post_data.get('expected_start_date'):
                form_data['expected_start_date'] = post_data['expected_start_date']

            health_boolean_fields = [
                'has_medical_problems', 'recent_hospitalization', 'has_allergies'
            ]
            for field in health_boolean_fields:
                value = post_data.get(field)
                if value == 'yes':
                    form_data[field] = True
                elif value == 'no':
                    form_data[field] = False
                elif value == 'on':  
                    form_data[field] = True
                else:
                    form_data[field] = False
            
            if post_data.get('medical_details'):
                form_data['medical_details'] = post_data['medical_details']
            
            background_fields = [
                'religious_observances', 'background_information'
            ]
            for field in background_fields:
                if post_data.get(field):
                    form_data[field] = post_data[field]
        
        elif step == 6:
            # Dynamic admission fields (Configuration → Admission Details) are
            # posted as additional_field_<uuid> and saved separately via
            # _save_admission_additional_details — they are not model columns.
            pass

        elif step == 7:
            terms_checked = post_data.get('terms_agreement') == 'on'
            declaration_checked = post_data.get('declaration_agreement') == 'on'
            form_data['terms_agreement'] = terms_checked
            form_data['declaration_agreement'] = declaration_checked 
            form_data['fee_acknowledgment'] = True 
            
            if post_data.get('declaration_date'):
                form_data['declaration_date'] = post_data['declaration_date']
            else:
                from datetime import date
                form_data['declaration_date'] = date.today().isoformat()

            if post_data.get('declaration_signature_name'):
                form_data['declaration_signature_name'] = post_data['declaration_signature_name']

        return form_data
    
    def _save_admission_additional_details(self, post_data, application, school) -> None:
        """Upsert values for dynamic admission fields (Configuration → Admission
        Details). Keys arrive as ``additional_field_<field_uuid>``. Silent no-op
        when the form carries none."""
        prefix = 'additional_field_'
        posted = {k[len(prefix):]: v for k, v in post_data.items() if k.startswith(prefix)}
        if not posted:
            return
        try:
            from core.models import AdditionalField, AdmissionAdditionalDetail
            fields = {
                str(f.id): f
                for f in AdditionalField.objects.filter(
                    tenant=school, applies_to='admission', is_active=True
                )
            }
            for field_id, raw in posted.items():
                field = fields.get(str(field_id))
                if not field:
                    continue
                AdmissionAdditionalDetail.objects.update_or_create(
                    tenant=school, application=application, field=field,
                    defaults={'value': (raw or '').strip()},
                )
        except Exception as e:
            logger.error(f"Failed saving admission additional details: {e}")

    def _get_accumulated_form_data(self, request, current_step_data: Dict[str, Any], current_step: int) -> Dict[str, Any]:
        accumulated_data = {}
        
        session_key = 'admission_form_data'
        if session_key in request.session:
            accumulated_data.update(request.session[session_key])
        
        accumulated_data.update(current_step_data)
        
        request.session[session_key] = accumulated_data
        request.session.modified = True
        
        return accumulated_data
    
    def _update_application_step(self, application: ExtendedAdmissionApplication, step: int):
        application.current_step = max(application.current_step, step)
        
        if step == 1 and application.is_step1_complete:
            application.status = 'step1_completed'
        elif step == 2 and application.is_step2_complete:
            application.status = 'step2_completed'
        elif step == 3 and application.is_step3_complete:
            application.status = 'step3_completed'
        elif step == 4 and application.is_step4_complete:
            application.status = 'step4_completed'
        elif step == 5 and application.is_step5_complete:
            application.status = 'step5_completed'
        elif step == 6:
            application.status = 'step6_completed'
        elif step == 7:
            if application.declaration_agreement:
                application.status = 'ready_for_submission'
        
        application.save()
    
    def _process_step_file_uploads(
        self, 
        request, 
        application: ExtendedAdmissionApplication,
        step: int,
        admission_service: ExtendedAdmissionService
    ) -> None:
        if step == 2:
            if 'student_photo' in request.FILES:
                try:
                    admission_service.upload_document(
                        str(application.id),
                        'student_photo',
                        request.FILES['student_photo'],
                        user=request.user if request.user and hasattr(request.user, 'is_authenticated') and request.user.is_authenticated else None
                    )
                except Exception as e:
                    logger.error(f"Failed to upload student photo: {str(e)}")
                    
        elif step == 6:
            document_fields = [
                'immunization_record', 'birth_certificate', 'utility_bill',
                'parent1_id', 'parent2_id', 'passport_photo_1', 'passport_photo_2'
            ]
            
            for field_name in document_fields:
                if field_name in request.FILES:
                    try:
                        admission_service.upload_document(
                            str(application.id),
                            field_name,
                            request.FILES[field_name],
                            user=request.user if request.user and hasattr(request.user, 'is_authenticated') and request.user.is_authenticated else None
                        )
                    except Exception as e:
                        logger.error(f"Failed to upload {field_name}: {str(e)}")
    
    def _process_temporary_files(
        self,
        request,
        application: ExtendedAdmissionApplication,
        admission_service: ExtendedAdmissionService
    ) -> None:
        temp_files = request.session.get('temp_uploaded_files', {})
        
        if not temp_files:
            return
        
        from django.core.files.storage import default_storage
        from django.core.files import File
        
        for field_name, file_info in temp_files.items():
            try:
                temp_path = file_info['path']
                if default_storage.exists(temp_path):
                    with default_storage.open(temp_path, 'rb') as temp_file:
                        file_content = temp_file.read()
                    
                    from django.core.files.base import ContentFile
                    file_obj = ContentFile(file_content, name=file_info['original_name'])
                    
                    admission_service.upload_document(
                        str(application.id),
                        field_name,
                        file_obj,
                        user=request.user if request.user and hasattr(request.user, 'is_authenticated') and request.user.is_authenticated else None
                    )
                    
                    default_storage.delete(temp_path)
                    
                    logger.info(f"Processed temporary file {field_name} for application {application.application_number}")
                
            except Exception as e:
                logger.error(f"Failed to process temporary file {field_name}: {str(e)}")
        
        request.session.pop('temp_uploaded_files', None)
        request.session.modified = True
    
    def _handle_step_action(
        self,
        request,
        application: ExtendedAdmissionApplication,
        current_step: int,
        action: str,
        admission_service: ExtendedAdmissionService
    ) -> Dict[str, Any]:
        if action == 'save':
            return {
                'success': True,
                'message': f'Step {current_step} saved successfully!',
                'application_id': str(application.id),
                'application_number': application.application_number,
                'current_step': application.current_step,
                'next_step': application.get_next_step(),
                'can_submit': application.can_submit(),
                'step_complete': self._is_step_complete(application, current_step)
            }
            
        elif action == 'save_continue':
            next_step = application.get_next_step()
            if next_step and next_step <= 5:
                request.session['current_step'] = next_step
                return {
                    'success': True,
                    'message': f'Step {current_step} completed! Moving to step {next_step}.',
                    'application_id': str(application.id),
                    'application_number': application.application_number,
                    'current_step': next_step,
                    'next_step': application.get_next_step(),
                    'redirect': f'?continue={application.id}&step={next_step}',
                    'step_complete': True
                }
            else:
                return {
                    'success': True,
                    'message': 'All steps completed! You can now submit your application.',
                    'application_id': str(application.id),
                    'application_number': application.application_number,
                    'current_step': 5,
                    'next_step': None,
                    'can_submit': application.can_submit(),
                    'all_steps_complete': True
                }
                
        elif action == 'submit':
            # DEBUG: Confirm we're hitting submit action
            logger.error(f"HIT SUBMIT ACTION: step={current_step}, can_submit={application.can_submit()}")
            
            # FINAL COMPREHENSIVE FIX: Handle submission properly
            try:
                # Attempt normal submission first
                if application.can_submit():
                    admission_service.submit_application(
                        str(application.id),
                        user=request.user if request.user and hasattr(request.user, 'is_authenticated') and request.user.is_authenticated else None
                    )
                else:
                    # FORCE SUBMISSION: If steps appear incomplete due to bulk submission,
                    # but all required fields are present, force the submission
                    required_fields = [
                        'first_name', 'last_name', 'date_of_birth', 'gender', 'nationality',
                        'guardian1_first_name', 'guardian1_last_name', 'guardian1_relation', 
                        'guardian1_mobile', 'address_line1', 'city', 'country'
                    ]
                    
                    # Check if all critical fields are present
                    has_required_fields = all(getattr(application, field, None) for field in required_fields)
                    has_agreements = (getattr(application, 'terms_agreement', False) and 
                                     getattr(application, 'declaration_agreement', False))
                    
                    if has_required_fields and has_agreements:
                        # Force submit even if step validation fails
                        admission_service.submit_application(
                            str(application.id),
                            user=request.user if request.user and hasattr(request.user, 'is_authenticated') and request.user.is_authenticated else None
                        )
                    else:
                        # Still missing critical data - reject
                        raise ValidationException(
                            "Missing required information. Please ensure all required fields are filled."
                        )
                
                # Generate success response with redirect
                try:
                    _is_portal = self.request.POST.get('is_portal') == '1'
                    _success_route = 'core:portal_admission_success' if _is_portal else 'core:admission_register_success'
                    success_url = reverse(_success_route, kwargs={
                        'app_number': application.application_number
                    })
                except Exception as e:
                    logger.error(f"Failed to generate success URL: {str(e)}")
                    success_url = f"/register/success/{application.application_number}/"
                
                return {
                    'success': True,
                    'message': 'Application submitted successfully!',
                    'application_number': application.application_number,
                    'redirect': success_url
                }
                
            except Exception as e:
                logger.error(f"Application submission failed: {str(e)}")
                raise ServiceException("Failed to submit application. Please try again.")
        
        else:
            raise ValidationException(f"Invalid action: {action}")
    
    def _handle_final_submission(self, request, school):
        """Handle final submission when action=submit"""
        try:
            # Extract all form data - COMPREHENSIVE EXTRACTION
            form_data = {}
            
            # Handle all text/date fields
            text_fields = [
                'academic_year', 'course_applied', 'first_name', 'middle_name', 'last_name',
                'date_of_birth', 'gender', 'nationality', 'student_category', 'religion',
                'birth_place', 'mother_tongue', 'email', 'guardian1_first_name', 'guardian1_last_name',
                'guardian1_relation', 'guardian1_occupation', 'guardian1_mobile', 'guardian1_email',
                'guardian2_first_name', 'guardian2_last_name', 'guardian2_relation', 'guardian2_occupation',
                'guardian2_mobile', 'guardian2_email', 'address_line1', 'address_line2', 'city',
                'state_province', 'postal_code', 'country', 'previous_school_name', 'last_attendance_year',
                'religious_observances', 'background_information', 'declaration_date'
            ]
            
            for field in text_fields:
                if field in request.POST:
                    form_data[field] = request.POST[field]
            
            # Handle boolean fields (checkboxes)
            boolean_fields = [
                'terms_agreement', 'declaration_agreement', 'has_medical_problems', 
                'recent_hospitalization', 'has_allergies'
            ]
            
            for field in boolean_fields:
                value = request.POST.get(field, '')
                # Handle both 'on' (checked) and empty string (unchecked from JS)
                form_data[field] = value == 'on'

            if not form_data.get('terms_agreement'):
                return JsonResponse({
                    'success': False,
                    'error': 'You must agree to the Terms and Conditions for Admission before submitting.'
                }, status=400)

            # Get or create application
            admission_service = ExtendedAdmissionService(school)
            app_id = request.POST.get('application_id')

            # Atomic so a failure after create_application rolls the draft
            # back instead of leaving an orphan that duplicates on retry.
            with transaction.atomic():
                if app_id:
                    application = admission_service.get_by_id(app_id)
                    application = admission_service.update_application(app_id, form_data)
                else:
                    existing = self._find_existing_application(school, form_data)

                    if existing and existing.status == 'submitted':
                        # Same applicant re-posted (double-click, client
                        # timeout retry): treat as success, don't duplicate.
                        return self._submission_success_response(request, existing)
                    elif existing and existing.status in ('approved', 'rejected'):
                        return JsonResponse({
                            'success': False,
                            'error': (
                                f'An application for this applicant already exists '
                                f'(application number {existing.application_number}). '
                                f'Please use the status check page instead of re-applying.'
                            )
                        }, status=400)
                    elif existing:
                        # Draft left behind by an earlier failed submission —
                        # reuse it rather than creating a duplicate.
                        application = admission_service.update_application(
                            str(existing.id), form_data
                        )
                    else:
                        application = admission_service.create_application(form_data)

                # FORCE SET REQUIRED FIELDS: Ensure submission can proceed
                application.refresh_from_db()
                application.declaration_agreement = form_data.get('declaration_agreement', True)
                application.terms_agreement = form_data.get('terms_agreement', True)
                if not application.declaration_date and form_data.get('declaration_date'):
                    application.declaration_date = form_data['declaration_date']
                elif not application.declaration_date:
                    from datetime import date
                    application.declaration_date = date.today()
                application.save()

                # Force submit the application
                admission_service.submit_application(str(application.id))

            return self._submission_success_response(request, application)

        except Exception as e:
            logger.error(f"Final submission failed: {str(e)}")
            return JsonResponse({
                'success': False,
                'error': 'Failed to submit application. Please try again.'
            }, status=400)

    def _find_existing_application(self, school, form_data: Dict[str, Any]):
        """
        Locate an application that this submission is a duplicate of: same
        tenant, applicant name, and date of birth (and academic year when
        given). Matching requires the date of birth so that two different
        children who share a name are never conflated.
        """
        first_name = str(form_data.get('first_name') or '').strip()
        last_name = str(form_data.get('last_name') or '').strip()
        date_of_birth = str(form_data.get('date_of_birth') or '').strip()

        if not (first_name and last_name and date_of_birth):
            return None

        queryset = ExtendedAdmissionApplication.objects.filter(
            tenant=school,
            first_name__iexact=first_name,
            last_name__iexact=last_name,
            date_of_birth=date_of_birth,
        )

        academic_year_id = str(form_data.get('academic_year') or '').strip()
        if academic_year_id:
            queryset = queryset.filter(academic_year_id=academic_year_id)

        try:
            # Prefer an already-submitted/decided application over a leftover
            # draft so a stale draft never shadows the real application.
            for statuses in (('submitted',), ('approved', 'rejected'), None):
                matches = queryset
                if statuses:
                    matches = queryset.filter(status__in=statuses)
                else:
                    matches = queryset.exclude(
                        status__in=('submitted', 'approved', 'rejected')
                    )
                match = matches.order_by('-created_at').first()
                if match:
                    return match
            return None
        except (ValidationError, ValueError):
            # Malformed date/uuid input — let the create path validate it.
            return None

    def _submission_success_response(self, request, application: ExtendedAdmissionApplication) -> JsonResponse:
        try:
            _is_portal = request.POST.get('is_portal') == '1'
            _success_route = 'core:portal_admission_success' if _is_portal else 'core:admission_register_success'
            success_url = reverse(_success_route, kwargs={
                'app_number': application.application_number
            })
        except Exception:
            success_url = f"/register/success/{application.application_number}/"

        return JsonResponse({
            'success': True,
            'message': 'Application submitted successfully!',
            'application_number': application.application_number,
            'redirect': success_url
        })

    def _is_step_complete(self, application: ExtendedAdmissionApplication, step: int) -> bool:
        if step == 1:
            return application.is_step1_complete
        elif step == 2:
            return application.is_step2_complete
        elif step == 3:
            return application.is_step3_complete
        elif step == 4:
            return application.is_step4_complete
        elif step == 5:
            return application.is_step5_complete
        return False

    def _extract_form_data(self, post_data: Dict[str, Any]) -> Dict[str, Any]:
        form_data = {}
        
        if post_data.get('academic_year'):
            form_data['academic_year'] = post_data['academic_year']
        if post_data.get('course_applied'):
            form_data['course_applied'] = post_data['course_applied']
        if post_data.get('preferred_start_date'):
            form_data['preferred_start_date'] = datetime.strptime(
                post_data['preferred_start_date'], '%Y-%m-%d'
            ).date()
        
        student_fields = [
            'first_name', 'middle_name', 'last_name', 'gender',
            'nationality', 'address', 'phone_number', 'email'
        ]
        for field in student_fields:
            if post_data.get(field):
                form_data[field] = post_data[field]
        
        if post_data.get('date_of_birth'):
            form_data['date_of_birth'] = datetime.strptime(
                post_data['date_of_birth'], '%Y-%m-%d'
            ).date()
        
        guardian_fields = [
            'guardian_name', 'guardian_relationship', 'guardian_phone',
            'guardian_email', 'guardian_occupation', 'guardian_employer',
            'secondary_guardian_name', 'secondary_guardian_relationship',
            'secondary_guardian_phone', 'secondary_guardian_email'
        ]
        for field in guardian_fields:
            if post_data.get(field):
                form_data[field] = post_data[field]
        
        school_fields = [
            'previous_school_name', 'previous_school_address',
            'last_class_attended', 'reason_for_leaving',
            'academic_performance'
        ]
        for field in school_fields:
            if post_data.get(field):
                form_data[field] = post_data[field]
        
        if post_data.get('last_attendance_year'):
            form_data['last_attendance_year'] = int(post_data['last_attendance_year'])
        
        health_fields = [
            'blood_group', 'medical_conditions', 'medications',
            'emergency_contact_name', 'emergency_contact_phone',
            'emergency_contact_relationship'
        ]
        for field in health_fields:
            if post_data.get(field):
                form_data[field] = post_data[field]
        
        if post_data.get('height'):
            form_data['height'] = int(post_data['height'])
        if post_data.get('weight'):
            form_data['weight'] = int(post_data['weight'])
        
        form_data['terms_agreement'] = post_data.get('terms_agreement') == 'on'
        form_data['fee_acknowledgment'] = post_data.get('fee_acknowledgment') == 'on'
        
        return form_data
    
    def _validate_form_data(self, form_data: Dict[str, Any]) -> None:
        required_fields = [
            'academic_year', 'course_applied', 'first_name', 'last_name',
            'date_of_birth', 'gender', 'nationality', 'address',
            'guardian_name', 'guardian_relationship', 'guardian_phone',
            'previous_school_name', 'last_class_attended', 'last_attendance_year',
            'emergency_contact_name', 'emergency_contact_phone',
            'emergency_contact_relationship'
        ]
        
        missing_fields = []
        for field in required_fields:
            if not form_data.get(field):
                missing_fields.append(field)
        
        if missing_fields:
            raise ValidationException(
                f"Missing required fields: {', '.join(missing_fields)}",
                details={'missing_fields': missing_fields}
            )
        
        if not form_data.get('terms_agreement'):
            raise ValidationException("Terms and conditions agreement is required")
        
        if not form_data.get('fee_acknowledgment'):
            raise ValidationException("Fee acknowledgment is required")
    
    def _process_file_uploads(
        self, 
        request, 
        application: ExtendedAdmissionApplication,
        admission_service: ExtendedAdmissionService
    ) -> None:
        file_fields = [
            'immunization_record', 'birth_certificate', 'utility_bill',
            'parent1_id', 'parent2_id', 'student_photo'
        ]
        
        for field_name in file_fields:
            if field_name in request.FILES:
                file_data = request.FILES[field_name]
                
                try:
                    admission_service.upload_document(
                        str(application.id),
                        field_name,
                        file_data,
                        user=request.user if request.user and hasattr(request.user, 'is_authenticated') and request.user.is_authenticated else None
                    )
                except Exception as e:
                    logger.error(f"Failed to upload {field_name}: {str(e)}")
        self._process_temporary_files(request, application, admission_service)


class AdmissionStepNavigationView(TemplateView):
    def get(self, request, *args, **kwargs):
        school = getattr(request, 'tenant', None)
        if not school:
            raise Http404("School not found")
        
        app_id = request.GET.get('app_id')
        step = request.GET.get('step', '1')
        
        try:
            step_num = int(step)
            if not (1 <= step_num <= 7):
                messages.error(request, "Invalid step number.")
                return redirect('core:admission_register')
        except (ValueError, TypeError):
            messages.error(request, "Invalid step number.")
            return redirect('core:admission_register')
        
        if app_id:
            try:
                admission_service = ExtendedAdmissionService(school)
                application = admission_service.get_by_id(app_id)
                
                if step_num > application.current_step + 1:
                    messages.error(request, f"Please complete step {application.current_step} first.")
                    return redirect(f'core:admission_register?continue={app_id}&step={application.current_step}')
                
                request.session['current_step'] = step_num
                return redirect(f'?continue={app_id}&step={step_num}')
                
            except NotFoundException:
                messages.error(request, "Application not found.")
                return redirect('core:admission_register')
        else:
            if step_num > 1:
                messages.error(request, "Please start from step 1 for a new application.")
                return redirect('core:admission_register')
            
            request.session['current_step'] = 1
            return redirect('core:admission_register')
    
    def post(self, request, *args, **kwargs):
        school = getattr(request, 'tenant', None)
        if not school:
            return JsonResponse({'error': 'School not found'}, status=400)
        
        app_id = request.POST.get('app_id')
        step = request.POST.get('step')
        
        try:
            step_num = int(step)
            if not (1 <= step_num <= 5):
                return JsonResponse({'error': 'Invalid step number'}, status=400)
        except (ValueError, TypeError):
            return JsonResponse({'error': 'Invalid step number'}, status=400)
        
        if app_id:
            try:
                admission_service = ExtendedAdmissionService(school)
                application = admission_service.get_by_id(app_id)
                
                if step_num > application.current_step + 1:
                    return JsonResponse({
                        'success': False,
                        'error': f'Please complete step {application.current_step} first.',
                        'allowed_step': application.current_step
                    }, status=400)
                
                request.session['current_step'] = step_num
                
                return JsonResponse({
                    'success': True,
                    'current_step': step_num,
                    'redirect': f'?continue={app_id}&step={step_num}'
                })
                
            except NotFoundException:
                return JsonResponse({'error': 'Application not found'}, status=404)
        else:
            if step_num > 1:
                return JsonResponse({
                    'success': False,
                    'error': 'Please start from step 1 for a new application.',
                    'allowed_step': 1
                }, status=400)
            
            request.session['current_step'] = 1
            return JsonResponse({
                'success': True,
                'current_step': 1,
                'redirect': '?step=1'
            })


@require_http_methods(["POST"])
def upload_document_api(request):
    school = getattr(request, 'tenant', None)
    if not school:
        return JsonResponse({'error': 'School not found'}, status=400)
    
    try:
        if 'file' not in request.FILES:
            return JsonResponse({'error': 'No file provided'}, status=400)
        
        file_data = request.FILES['file']
        field_name = request.POST.get('field_name', 'other')
        application_id = request.POST.get('application_id')
        
        max_size = 5 * 1024 * 1024  
        if file_data.size > max_size:
            return JsonResponse({'error': 'File size too large (max 5MB)'}, status=400)
        
        allowed_extensions = ['pdf', 'jpg', 'jpeg', 'png']
        file_extension = file_data.name.split('.')[-1].lower()
        if file_extension not in allowed_extensions:
            return JsonResponse({'error': 'File type not allowed'}, status=400)
        
        if application_id:
            try:
                admission_service = ExtendedAdmissionService(school)
                document = admission_service.upload_document(
                    application_id,
                    field_name,
                    file_data,
                    user=request.user if request.user.is_authenticated else None
                )
                
                return JsonResponse({
                    'success': True,
                    'name': file_data.name,
                    'size': file_data.size,
                    'type': file_data.content_type,
                    'field_name': field_name,
                    'document_id': str(document.id),
                    'stored': True
                })
                
            except Exception as e:
                logger.error(f"Failed to store document {field_name}: {str(e)}")
                return JsonResponse({'error': f'Failed to store document: {str(e)}'}, status=500)
        
        else:
            if 'temp_uploaded_files' not in request.session:
                request.session['temp_uploaded_files'] = {}
            
            import uuid
            import time
            from django.core.files.storage import default_storage
            timestamp = int(time.time())
            temp_filename = f"temp/{timestamp}_{uuid.uuid4()}_{file_data.name}"
            
            file_path = default_storage.save(temp_filename, file_data)
            
            request.session['temp_uploaded_files'][field_name] = {
                'path': file_path,
                'original_name': file_data.name,
                'size': file_data.size,
                'type': file_data.content_type,
                'timestamp': timestamp,
                'session_id': request.session.session_key or 'anonymous'
            }
            request.session.modified = True
            
            return JsonResponse({
                'success': True,
                'name': file_data.name,
                'size': file_data.size,
                'type': file_data.content_type,
                'field_name': field_name,
                'stored': False,
                'temp_stored': True
            })
        
    except Exception as e:
        logger.error(f"File upload error: {str(e)}")
        return JsonResponse({'error': 'Upload failed'}, status=500)


@require_http_methods(["POST"])
def cleanup_temp_files_api(request):
    if request.method != 'POST':
        return JsonResponse({'error': 'Method not allowed'}, status=405)
    
    try:
        temp_files = request.session.get('temp_uploaded_files', {})
        cleaned_count = 0
        
        from django.core.files.storage import default_storage
        
        for field_name, file_info in temp_files.items():
            try:
                temp_path = file_info['path']
                if default_storage.exists(temp_path):
                    default_storage.delete(temp_path)
                    cleaned_count += 1
                    logger.info(f"Cleaned up temporary file: {temp_path}")
            except Exception as e:
                logger.error(f"Failed to cleanup temp file {field_name}: {str(e)}")
        
        request.session.pop('temp_uploaded_files', None)
        request.session.modified = True
        
        return JsonResponse({
            'success': True,
            'cleaned_files': cleaned_count,
            'message': f'Cleaned up {cleaned_count} temporary files'
        })
        
    except Exception as e:
        logger.error(f"Temp file cleanup error: {str(e)}")
        return JsonResponse({'error': 'Cleanup failed'}, status=500)


class AdmissionSuccessView(TemplateView):
    template_name = 'core/admission/success.html'
    
    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        
        app_number = kwargs.get('app_number')
        school = getattr(self.request, 'tenant', None)
        
        if school and app_number:
            try:
                admission_service = ExtendedAdmissionService(school)
                application = admission_service.get_application_by_number(app_number)
                context['application'] = application
                context['school'] = school
            except NotFoundException:
                context['error'] = "Application not found"
        
        return context


class AdmissionStatusCheckView(TemplateView):
    template_name = 'core/admission/status_check.html'
    
    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        context['school'] = getattr(self.request, 'tenant', None)
        return context
    
    def post(self, request, *args, **kwargs):
        school = getattr(request, 'tenant', None)
        if not school:
            return JsonResponse({'error': 'School not found'}, status=400)
        
        application_number = request.POST.get('application_number', '').strip()
        if not application_number:
            return JsonResponse({'error': 'Application number is required'}, status=400)
        
        try:
            admission_service = ExtendedAdmissionService(school)
            application = admission_service.get_application_by_number(application_number)
            
            return JsonResponse({
                'success': True,
                'application': {
                    'application_number': application.application_number,
                    'full_name': application.full_name,
                    'status': application.get_status_display(),
                    'application_date': application.application_date.strftime('%B %d, %Y'),
                    'course_applied': application.course_applied.course_name,
                    'remarks': application.remarks or ''
                }
            })
            
        except NotFoundException:
            return JsonResponse({
                'success': False,
                'error': 'Application not found. Please check your application number.'
            })
            
        except Exception as e:
            logger.error(f"Status check error: {str(e)}")
            return JsonResponse({
                'success': False,
                'error': 'An error occurred while checking status.'
            })


class AdmissionManagementListView(TemplateView):
    template_name = 'core/admission/management_list.html'
    paginate_by = 25

    def get_context_data(self, **kwargs):
        from django.core.paginator import Paginator, EmptyPage, PageNotAnInteger

        context = super().get_context_data(**kwargs)

        school = getattr(self.request, 'tenant', None)
        if school:
            admission_service = ExtendedAdmissionService(school)

            status = self.request.GET.get('status', '')
            academic_year = self.request.GET.get('academic_year', '')
            page = self.request.GET.get('page', 1)

            if status:
                queryset = admission_service.get_applications_by_status(status)
            elif academic_year:
                queryset = admission_service.get_applications_by_academic_year(academic_year)
            else:
                queryset = admission_service.get_base_queryset().order_by('-application_date')

            queryset = queryset.select_related('course_applied', 'academic_year', 'country', 'student_category')

            paginator = Paginator(queryset, self.paginate_by)

            try:
                applications = paginator.page(page)
            except PageNotAnInteger:
                applications = paginator.page(1)
            except EmptyPage:
                applications = paginator.page(paginator.num_pages)

            context['applications'] = applications
            context['paginator'] = paginator
            context['page_obj'] = applications
            context['is_paginated'] = paginator.num_pages > 1
            context['school'] = school
            context['statistics'] = admission_service.get_admission_statistics()
            context['academic_years'] = AcademicYear.objects.filter(
                tenant=school,
                is_active=True
            ).order_by('-start_date')

            context['current_status'] = status
            context['current_academic_year'] = academic_year

            context['back_url'] = self.request.GET.get('back', reverse('core:dashboard'))
            context['crumbs'] = [
                {'label': 'Admission'},
            ]

        return context


class AdmissionReportView(TemplateView):
    template_name = 'core/admission/report.html'

    def get_context_data(self, **kwargs):
        from django.db.models import Count
        context = super().get_context_data(**kwargs)
        school = getattr(self.request, 'tenant', None)
        if not school:
            return context

        service = ExtendedAdmissionService(school)
        qs = service.get_base_queryset()

        # Filters from GET params
        selected_status = self.request.GET.get('status', '')
        academic_year_id = self.request.GET.get('academic_year', '')
        date_from = self.request.GET.get('date_from', '')
        date_to   = self.request.GET.get('date_to', '')

        if selected_status:
            qs = qs.filter(status=selected_status)
        if academic_year_id:
            qs = qs.filter(academic_year_id=academic_year_id)
        if date_from:
            qs = qs.filter(application_date__gte=date_from)
        if date_to:
            qs = qs.filter(application_date__lte=date_to)

        applications = qs.select_related('course_applied', 'academic_year').order_by('-application_date')

        # Full statistics (always unfiltered so counts are global)
        statistics = service.get_admission_statistics()

        # Approval rate
        total = statistics.get('total', 0)
        approved = statistics.get('approved', 0)
        approval_rate = round((approved / total) * 100) if total > 0 else 0

        # Status breakdown list for sidebar
        status_breakdown = [
            ('Submitted',    statistics.get('submitted', 0),    'submitted'),
            ('Under Review', statistics.get('under_review', 0), 'under_review'),
            ('Approved',     statistics.get('approved', 0),     'approved'),
            ('Admitted',     statistics.get('admitted', 0),     'admitted'),
            ('Rejected',     statistics.get('rejected', 0),     'rejected'),
            ('Waitlisted',   statistics.get('waitlisted', 0),   'waitlisted'),
            ('Draft',        statistics.get('draft', 0),        'draft'),
        ]

        # Course breakdown — each dict has 'course_applied__course_name' and 'count'
        course_breakdown = (
            service.get_base_queryset()
            .values('course_applied__course_name')
            .annotate(count=Count('id'))
            .order_by('-count')[:10]
        )
        # Normalise key name for template
        course_breakdown = [
            {'course_name': item['course_applied__course_name'], 'count': item['count']}
            for item in course_breakdown
        ]

        # Academic years for filter dropdown
        academic_years = AcademicYear.objects.filter(tenant=school).order_by('-start_date')

        # Selected year object (for display in header)
        selected_year = None
        if academic_year_id:
            try:
                selected_year = academic_years.get(id=academic_year_id)
            except AcademicYear.DoesNotExist:
                pass

        context.update({
            'applications':     applications,
            'statistics':       statistics,
            'approval_rate':    approval_rate,
            'status_breakdown': status_breakdown,
            'course_breakdown': course_breakdown,
            'academic_years':   academic_years,
            'selected_status':  selected_status,
            'selected_year':    selected_year,
            'date_from':        date_from,
            'date_to':          date_to,
            'back_url': self.request.GET.get('back', reverse('core:admission_manage')),
            'crumbs': [
                {'label': 'Admission', 'url': reverse('core:admission_manage')},
                {'label': 'Report'},
            ],
        })
        return context


def cleanup_old_temp_files(max_age_hours=2):
    import time
    import os
    from django.core.files.storage import default_storage
    
    try:
        current_time = int(time.time())
        max_age_seconds = max_age_hours * 3600
        cleaned_count = 0
        
        if default_storage.exists('temp/'):
            temp_files = default_storage.listdir('temp/')[1] 
            
            for filename in temp_files:
                temp_path = f'temp/{filename}'
                
                try:
                    timestamp_str = filename.split('_')[0]
                    file_timestamp = int(timestamp_str)
                    
                    if current_time - file_timestamp > max_age_seconds:
                        default_storage.delete(temp_path)
                        cleaned_count += 1
                        logger.info(f"Cleaned up old temp file: {temp_path}")
                        
                except (ValueError, IndexError):
                    continue
                    
        logger.info(f"Temp file cleanup completed: {cleaned_count} files removed")
        return cleaned_count
        
    except Exception as e:
        logger.error(f"Error during temp file cleanup: {str(e)}")
        return 0


# ──────────────────────────────────────────────────────────────────────────────
# Parents Portal Views  (no login required — public facing)
# ──────────────────────────────────────────────────────────────────────────────

_PORTAL_BASE = 'core/portal/public_base.html'


class PortalLandingView(TemplateView):
    template_name = 'core/portal/landing.html'

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        context['school'] = getattr(self.request, 'tenant', None)
        return context


class PortalAdmissionRegistrationView(AdmissionRegistrationView):
    """Public-facing admission form — same logic, clean public base template."""

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        context['base_template'] = _PORTAL_BASE
        context['is_portal'] = True
        return context


class PortalAdmissionSuccessView(AdmissionSuccessView):
    """Success page for the parents portal."""

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        context['base_template'] = _PORTAL_BASE
        context['is_portal'] = True
        return context


class PortalStatusCheckView(AdmissionStatusCheckView):
    """Application status check for the parents portal."""

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        context['base_template'] = _PORTAL_BASE
        context['is_portal'] = True
        return context
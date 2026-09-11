"""
Diagnostic views for the admission system
Helps administrators check system readiness and troubleshoot issues
"""
import logging
from datetime import date

from django.shortcuts import render
from django.http import JsonResponse, Http404
from django.views.generic import TemplateView
from django.contrib import messages
from django.db import transaction

from core.models import School, AcademicYear, Course, Country, StudentCategory, ExtendedAdmissionApplication
from core.utils.data_initialization import (
    ensure_basic_data_exists, 
    check_admission_prerequisites,
    initialize_school_data
)

logger = logging.getLogger(__name__)


class AdmissionDiagnosticsView(TemplateView):
    """
    Diagnostic view for checking admission system status
    """
    template_name = 'core/admission/diagnostics.html'
    
    def get_context_data(self, **kwargs):
        from django.urls import reverse
        context = super().get_context_data(**kwargs)

        school = getattr(self.request, 'tenant', None)
        if not school:
            raise Http404("School not found")

        context['school'] = school

        # Run comprehensive diagnostics
        context['diagnostics'] = self.run_diagnostics(school)

        # Get application statistics
        context['application_stats'] = self.get_application_statistics(school)

        context['back_url'] = self.request.GET.get('back', reverse('core:admission_manage'))
        context['crumbs'] = [
            {'label': 'Admission', 'url': reverse('core:admission_manage')},
            {'label': 'Diagnostics'},
        ]

        return context
    
    def run_diagnostics(self, school: School) -> dict:
        """Run comprehensive diagnostics for the admission system"""
        diagnostics = {
            'overall_status': 'unknown',
            'checks': [],
            'warnings': [],
            'errors': [],
            'recommendations': []
        }
        
        try:
            # Check prerequisites
            prereq_check = check_admission_prerequisites(school)
            
            # Academic Years Check
            academic_years = AcademicYear.objects.filter(tenant=school, is_active=True)
            if academic_years.exists():
                diagnostics['checks'].append({
                    'name': 'Academic Years',
                    'status': 'pass',
                    'message': f'{academic_years.count()} active academic year(s) found',
                    'details': [f"• {ay.name} ({ay.start_date} to {ay.end_date})" for ay in academic_years]
                })
            else:
                diagnostics['errors'].append({
                    'name': 'Academic Years',
                    'message': 'No active academic years found',
                    'fix': 'Create academic years using the management interface or run setup command'
                })
            
            # Courses Check
            courses = Course.objects.filter(tenant=school, is_deleted=False)
            if courses.exists():
                diagnostics['checks'].append({
                    'name': 'Courses',
                    'status': 'pass',
                    'message': f'{courses.count()} course(s) available',
                    'details': [f"• {course.course_name} ({course.code})" for course in courses[:10]]
                })
                if courses.count() > 10:
                    diagnostics['checks'][-1]['details'].append(f"... and {courses.count() - 10} more")
            else:
                diagnostics['errors'].append({
                    'name': 'Courses',
                    'message': 'No courses available',
                    'fix': 'Create courses using the management interface'
                })
            
            # Countries Check
            countries = Country.objects.all()
            if countries.exists():
                diagnostics['checks'].append({
                    'name': 'Countries',
                    'status': 'pass',
                    'message': f'{countries.count()} countries available',
                    'details': [country.name for country in countries[:5]]
                })
                if countries.count() > 5:
                    diagnostics['checks'][-1]['details'].append(f"... and {countries.count() - 5} more")
            else:
                diagnostics['errors'].append({
                    'name': 'Countries',
                    'message': 'No countries available',
                    'fix': 'Run the setup_basic_data management command'
                })
            
            # Student Categories Check
            categories = StudentCategory.objects.filter(tenant=school, is_deleted=False)
            if categories.exists():
                diagnostics['checks'].append({
                    'name': 'Student Categories',
                    'status': 'pass',
                    'message': f'{categories.count()} student categories available',
                    'details': [cat.name for cat in categories]
                })
            else:
                diagnostics['warnings'].append({
                    'name': 'Student Categories',
                    'message': 'No student categories defined',
                    'fix': 'Student categories are optional but recommended for organization'
                })
            
            # Admission Settings Check
            current_date = date.today()
            admission_open = False
            for ay in academic_years:
                if ay.admission_start_date and ay.admission_end_date:
                    if ay.admission_start_date <= current_date <= ay.admission_end_date:
                        admission_open = True
                        diagnostics['checks'].append({
                            'name': 'Admission Period',
                            'status': 'pass',
                            'message': f'Admissions are open for {ay.name}',
                            'details': [f"Period: {ay.admission_start_date} to {ay.admission_end_date}"]
                        })
                        break
            
            if not admission_open:
                diagnostics['warnings'].append({
                    'name': 'Admission Period',
                    'message': 'No admission periods are currently open',
                    'fix': 'Check academic year admission dates or create new academic year'
                })
            
            # Overall Status
            if diagnostics['errors']:
                diagnostics['overall_status'] = 'error'
                diagnostics['recommendations'].append(
                    'Fix the errors above before proceeding with admission applications.'
                )
            elif diagnostics['warnings']:
                diagnostics['overall_status'] = 'warning'
                diagnostics['recommendations'].append(
                    'System is functional but some improvements are recommended.'
                )
            else:
                diagnostics['overall_status'] = 'pass'
                diagnostics['recommendations'].append(
                    'System is ready for admission applications!'
                )
            
            return diagnostics
            
        except Exception as e:
            logger.error(f"Error running diagnostics: {str(e)}")
            diagnostics['overall_status'] = 'error'
            diagnostics['errors'].append({
                'name': 'System Error',
                'message': f'Error running diagnostics: {str(e)}',
                'fix': 'Check system logs for more details'
            })
            return diagnostics
    
    def get_application_statistics(self, school: School) -> dict:
        """Get admission application statistics"""
        try:
            applications = ExtendedAdmissionApplication.objects.filter(tenant=school)
            
            stats = {
                'total_applications': applications.count(),
                'draft_applications': applications.filter(status__in=[
                    'draft', 'step1_completed', 'step2_completed', 
                    'step3_completed', 'step4_completed', 'step5_completed'
                ]).count(),
                'submitted_applications': applications.filter(status='submitted').count(),
                'approved_applications': applications.filter(status='approved').count(),
                'rejected_applications': applications.filter(status='rejected').count(),
                'recent_applications': applications.filter(
                    application_date__gte=date.today().replace(day=1)
                ).count()
            }
            
            # Get status breakdown
            status_breakdown = {}
            for status_choice in ExtendedAdmissionApplication._meta.get_field('status').choices:
                status_key = status_choice[0]
                status_label = status_choice[1]
                count = applications.filter(status=status_key).count()
                if count > 0:
                    status_breakdown[status_label] = count
            
            stats['status_breakdown'] = status_breakdown
            
            return stats
            
        except Exception as e:
            logger.error(f"Error getting application statistics: {str(e)}")
            return {
                'error': str(e),
                'total_applications': 0,
                'draft_applications': 0,
                'submitted_applications': 0,
                'approved_applications': 0,
                'rejected_applications': 0,
                'recent_applications': 0,
                'status_breakdown': {}
            }
    
    def post(self, request, *args, **kwargs):
        """Handle diagnostic actions like fixing data issues"""
        school = getattr(request, 'tenant', None)
        if not school:
            return JsonResponse({'error': 'School not found'}, status=400)
        
        action = request.POST.get('action')
        
        try:
            if action == 'initialize_data':
                with transaction.atomic():
                    success = initialize_school_data(school, create_sample_data=True)
                    
                    if success:
                        messages.success(
                            request, 
                            'Basic data has been initialized successfully!'
                        )
                        return JsonResponse({
                            'success': True,
                            'message': 'Data initialized successfully',
                            'redirect': request.path
                        })
                    else:
                        return JsonResponse({
                            'success': False,
                            'error': 'Failed to initialize data. Check logs for details.'
                        })
            
            elif action == 'ensure_basic_data':
                success = ensure_basic_data_exists(school)
                
                if success:
                    messages.success(
                        request, 
                        'Basic data check completed successfully!'
                    )
                    return JsonResponse({
                        'success': True,
                        'message': 'Basic data ensured',
                        'redirect': request.path
                    })
                else:
                    return JsonResponse({
                        'success': False,
                        'error': 'Failed to ensure basic data exists. Check logs.'
                    })
            
            else:
                return JsonResponse({
                    'success': False,
                    'error': f'Unknown action: {action}'
                })
        
        except Exception as e:
            logger.error(f"Error handling diagnostic action '{action}': {str(e)}")
            return JsonResponse({
                'success': False,
                'error': f'Error: {str(e)}'
            })
    

class AdmissionDataStatusAPI(TemplateView):
    """
    API endpoint to check admission data status
    Returns JSON response with system readiness status
    """
    
    def get(self, request, *args, **kwargs):
        school = getattr(request, 'tenant', None)
        if not school:
            return JsonResponse({'error': 'School not found'}, status=400)
        
        try:
            prereq_check = check_admission_prerequisites(school)
            
            return JsonResponse({
                'school_code': school.code,
                'school_name': school.name,
                'ready_for_admissions': prereq_check['ready'],
                'missing_requirements': prereq_check['missing'],
                'warnings': prereq_check['warnings'],
                'data_counts': prereq_check['counts']
            })
            
        except Exception as e:
            logger.error(f"Error checking admission data status: {str(e)}")
            return JsonResponse({
                'error': str(e),
                'ready_for_admissions': False
            }, status=500)
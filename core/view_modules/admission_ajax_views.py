"""
AJAX views for admission system quick actions
Handles CRUD operations for academic years, courses, etc.
"""
import logging
from datetime import datetime, date

from django.http import JsonResponse
from django.views.decorators.http import require_http_methods
from django.views.decorators.csrf import csrf_exempt
from django.utils.decorators import method_decorator
from django.views import View
from django.db import transaction

from core.models import AcademicYear, Course, Country, StudentCategory, School
from core.utils.data_initialization import ensure_basic_data_exists, initialize_school_data

logger = logging.getLogger(__name__)


class AcademicYearAjaxView(View):
    """AJAX view for academic year operations"""
    
    @method_decorator(csrf_exempt)
    def dispatch(self, *args, **kwargs):
        return super().dispatch(*args, **kwargs)
    
    def get(self, request, *args, **kwargs):
        """Get academic years for a school"""
        school = getattr(request, 'tenant', None)
        if not school:
            return JsonResponse({'error': 'School not found'}, status=400)
        
        try:
            academic_years = AcademicYear.objects.filter(tenant=school).order_by('-start_date')
            
            data = [{
                'id': str(ay.id),
                'name': ay.name,
                'start_date': ay.start_date.isoformat(),
                'end_date': ay.end_date.isoformat(),
                'is_active': ay.is_active,
                'admission_start_date': ay.admission_start_date.isoformat() if ay.admission_start_date else None,
                'admission_end_date': ay.admission_end_date.isoformat() if ay.admission_end_date else None,
            } for ay in academic_years]
            
            return JsonResponse({
                'success': True,
                'academic_years': data,
                'count': len(data)
            })
            
        except Exception as e:
            logger.error(f"Error fetching academic years: {str(e)}")
            return JsonResponse({'error': str(e)}, status=500)
    
    def post(self, request, *args, **kwargs):
        """Create a new academic year"""
        school = getattr(request, 'tenant', None)
        if not school:
            return JsonResponse({'error': 'School not found'}, status=400)
        
        try:
            with transaction.atomic():
                # Extract data from request
                name = request.POST.get('name', '').strip()
                start_date = request.POST.get('start_date')
                end_date = request.POST.get('end_date')
                admission_start_date = request.POST.get('admission_start_date')
                admission_end_date = request.POST.get('admission_end_date')
                is_active = request.POST.get('is_active', 'true').lower() == 'true'
                
                # Validation
                if not name:
                    return JsonResponse({
                        'success': False,
                        'error': 'Academic year name is required'
                    }, status=400)
                
                if not start_date or not end_date:
                    return JsonResponse({
                        'success': False,
                        'error': 'Start date and end date are required'
                    }, status=400)
                
                # Check for duplicates
                if AcademicYear.objects.filter(tenant=school, name=name).exists():
                    return JsonResponse({
                        'success': False,
                        'error': f'Academic year "{name}" already exists'
                    }, status=400)
                
                # Parse dates
                try:
                    start_date_obj = datetime.strptime(start_date, '%Y-%m-%d').date()
                    end_date_obj = datetime.strptime(end_date, '%Y-%m-%d').date()
                    
                    admission_start_date_obj = None
                    if admission_start_date:
                        admission_start_date_obj = datetime.strptime(admission_start_date, '%Y-%m-%d').date()
                    
                    admission_end_date_obj = None
                    if admission_end_date:
                        admission_end_date_obj = datetime.strptime(admission_end_date, '%Y-%m-%d').date()
                        
                except ValueError:
                    return JsonResponse({
                        'success': False,
                        'error': 'Invalid date format. Please use YYYY-MM-DD format.'
                    }, status=400)
                
                # Validate date logic
                if start_date_obj >= end_date_obj:
                    return JsonResponse({
                        'success': False,
                        'error': 'Start date must be before end date'
                    }, status=400)
                
                # Create academic year
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
                        'is_active': academic_year.is_active,
                        'admission_start_date': academic_year.admission_start_date.isoformat() if academic_year.admission_start_date else None,
                        'admission_end_date': academic_year.admission_end_date.isoformat() if academic_year.admission_end_date else None,
                    }
                })
                
        except Exception as e:
            logger.error(f"Error creating academic year: {str(e)}")
            return JsonResponse({
                'success': False,
                'error': f'Failed to create academic year: {str(e)}'
            }, status=500)


class CourseAjaxView(View):
    """AJAX view for course operations"""
    
    @method_decorator(csrf_exempt)
    def dispatch(self, *args, **kwargs):
        return super().dispatch(*args, **kwargs)
    
    def get(self, request, *args, **kwargs):
        """Get courses for a school"""
        school = getattr(request, 'tenant', None)
        if not school:
            return JsonResponse({'error': 'School not found'}, status=400)
        
        try:
            courses = Course.objects.filter(tenant=school, is_deleted=False).order_by('course_name')
            
            data = [{
                'id': str(course.id),
                'course_name': course.course_name,
                'code': course.code,
                'section_name': course.section_name,
            } for course in courses]
            
            return JsonResponse({
                'success': True,
                'courses': data,
                'count': len(data)
            })
            
        except Exception as e:
            logger.error(f"Error fetching courses: {str(e)}")
            return JsonResponse({'error': str(e)}, status=500)
    
    def post(self, request, *args, **kwargs):
        """Create a new course"""
        school = getattr(request, 'tenant', None)
        if not school:
            return JsonResponse({'error': 'School not found'}, status=400)
        
        try:
            with transaction.atomic():
                # Extract data from request
                course_name = request.POST.get('course_name', '').strip()
                code = request.POST.get('code', '').strip().upper()
                section_name = request.POST.get('section_name', '').strip()
                
                # Validation
                if not course_name:
                    return JsonResponse({
                        'success': False,
                        'error': 'Course name is required'
                    }, status=400)
                
                if not code:
                    return JsonResponse({
                        'success': False,
                        'error': 'Course code is required'
                    }, status=400)
                
                # Check for duplicates
                if Course.objects.filter(tenant=school, code=code).exists():
                    return JsonResponse({
                        'success': False,
                        'error': f'Course with code "{code}" already exists'
                    }, status=400)
                
                # Create course
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
            }, status=500)


@require_http_methods(["POST"])
@csrf_exempt
def initialize_basic_data_ajax(request):
    """AJAX endpoint to initialize basic data for a school"""
    school = getattr(request, 'tenant', None)
    if not school:
        return JsonResponse({'error': 'School not found'}, status=400)
    
    try:
        with transaction.atomic():
            # Initialize comprehensive data
            success = initialize_school_data(school, create_sample_data=True)
            
            if success:
                # Get updated counts
                academic_years_count = AcademicYear.objects.filter(tenant=school, is_active=True).count()
                courses_count = Course.objects.filter(tenant=school, is_deleted=False).count()
                categories_count = StudentCategory.objects.filter(tenant=school, is_deleted=False).count()
                countries_count = Country.objects.count()
                
                return JsonResponse({
                    'success': True,
                    'message': 'Basic data has been initialized successfully!',
                    'data_counts': {
                        'academic_years': academic_years_count,
                        'courses': courses_count,
                        'student_categories': categories_count,
                        'countries': countries_count
                    },
                    'reload_required': True
                })
            else:
                return JsonResponse({
                    'success': False,
                    'error': 'Failed to initialize basic data. Check system logs for details.'
                }, status=500)
                
    except Exception as e:
        logger.error(f"Error initializing basic data via AJAX: {str(e)}")
        return JsonResponse({
            'success': False,
            'error': f'Failed to initialize data: {str(e)}'
        }, status=500)


@require_http_methods(["GET"])
def admission_data_status_ajax(request):
    """AJAX endpoint to check admission data readiness"""
    school = getattr(request, 'tenant', None)
    if not school:
        return JsonResponse({'error': 'School not found'}, status=400)
    
    try:
        # Get current data counts
        academic_years_count = AcademicYear.objects.filter(tenant=school, is_active=True).count()
        courses_count = Course.objects.filter(tenant=school, is_deleted=False).count()
        categories_count = StudentCategory.objects.filter(tenant=school, is_deleted=False).count()
        countries_count = Country.objects.count()
        
        # Determine readiness
        ready = academic_years_count > 0 and courses_count > 0 and countries_count > 0
        
        warnings = []
        errors = []
        
        if academic_years_count == 0:
            errors.append('No active academic years found')
        if courses_count == 0:
            errors.append('No courses available')
        if countries_count == 0:
            errors.append('No countries available')
        if categories_count == 0:
            warnings.append('No student categories defined (recommended but not required)')
        
        return JsonResponse({
            'success': True,
            'ready': ready,
            'data_counts': {
                'academic_years': academic_years_count,
                'courses': courses_count,
                'student_categories': categories_count,
                'countries': countries_count
            },
            'warnings': warnings,
            'errors': errors
        })
        
    except Exception as e:
        logger.error(f"Error checking admission data status: {str(e)}")
        return JsonResponse({
            'success': False,
            'error': str(e)
        }, status=500)


@require_http_methods(["POST"])
@csrf_exempt 
def create_quick_academic_year_ajax(request):
    """Quick AJAX endpoint to create current/next academic year"""
    school = getattr(request, 'tenant', None)
    if not school:
        return JsonResponse({'error': 'School not found'}, status=400)
    
    try:
        with transaction.atomic():
            current_year = date.today().year
            
            # Create current academic year if it doesn't exist
            current_ay_name = f"{current_year}-{current_year + 1}"
            
            if not AcademicYear.objects.filter(tenant=school, name=current_ay_name).exists():
                academic_year = AcademicYear.objects.create(
                    tenant=school,
                    name=current_ay_name,
                    start_date=date(current_year, 9, 1),
                    end_date=date(current_year + 1, 6, 30),
                    is_active=True,
                    admission_start_date=date(current_year, 1, 1),
                    admission_end_date=date(current_year, 8, 31)
                )
                
                logger.info(f"Quick-created academic year {academic_year.name} for school {school.code}")
                
                return JsonResponse({
                    'success': True,
                    'message': f'Academic year "{current_ay_name}" created successfully!',
                    'academic_year': {
                        'id': str(academic_year.id),
                        'name': academic_year.name,
                        'start_date': academic_year.start_date.isoformat(),
                        'end_date': academic_year.end_date.isoformat(),
                        'is_active': academic_year.is_active
                    }
                })
            else:
                return JsonResponse({
                    'success': False,
                    'error': f'Academic year "{current_ay_name}" already exists'
                }, status=400)
                
    except Exception as e:
        logger.error(f"Error creating quick academic year: {str(e)}")
        return JsonResponse({
            'success': False,
            'error': f'Failed to create academic year: {str(e)}'
        }, status=500)
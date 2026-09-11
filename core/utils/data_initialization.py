"""
Utility functions for initializing basic data required by the admission system.
This module provides functions that can be called during application startup
or when setting up new schools to ensure required data exists.
"""
import logging
from datetime import date
from typing import Optional

from core.models import School, AcademicYear, Country, StudentCategory, Course

logger = logging.getLogger(__name__)


def initialize_countries():
    """
    Initialize basic countries data if it doesn't exist.
    This is safe to call multiple times.
    """
    countries_data = [
        {'name': 'Zambia', 'code': 'ZM'},
        {'name': 'South Africa', 'code': 'ZA'},
        {'name': 'Kenya', 'code': 'KE'},
        {'name': 'Tanzania', 'code': 'TZ'},
        {'name': 'Uganda', 'code': 'UG'},
        {'name': 'Botswana', 'code': 'BW'},
        {'name': 'Namibia', 'code': 'NA'},
        {'name': 'Zimbabwe', 'code': 'ZW'},
        {'name': 'Malawi', 'code': 'MW'},
        {'name': 'Mozambique', 'code': 'MZ'},
        {'name': 'United Kingdom', 'code': 'GB'},
        {'name': 'United States', 'code': 'US'},
        {'name': 'Canada', 'code': 'CA'},
        {'name': 'Australia', 'code': 'AU'},
        {'name': 'India', 'code': 'IN'},
        {'name': 'Other', 'code': 'XX'},
    ]
    
    created_count = 0
    try:
        for country_data in countries_data:
            country, created = Country.objects.get_or_create(
                code=country_data['code'],
                defaults={'name': country_data['name']}
            )
            if created:
                created_count += 1
                logger.info(f"Created country: {country.name}")
        
        logger.info(f"Countries initialized: {created_count} created, {Country.objects.count()} total")
        return True
        
    except Exception as e:
        logger.error(f"Error initializing countries: {str(e)}")
        return False


def initialize_school_data(school: School, create_sample_data: bool = True):
    """
    Initialize basic data for a specific school.
    
    Args:
        school: The School instance to initialize data for
        create_sample_data: Whether to create sample data or minimal data only
    
    Returns:
        bool: True if initialization was successful, False otherwise
    """
    try:
        # Initialize academic years
        academic_years_created = _initialize_academic_years(school)
        
        # Initialize courses
        courses_created = _initialize_courses(school, create_sample_data)
        
        # Initialize student categories
        categories_created = _initialize_student_categories(school, create_sample_data)
        
        logger.info(
            f"School {school.code} data initialized: "
            f"{academic_years_created} academic years, "
            f"{courses_created} courses, "
            f"{categories_created} student categories"
        )
        
        return True
        
    except Exception as e:
        logger.error(f"Error initializing data for school {school.code}: {str(e)}")
        return False


def _initialize_academic_years(school: School) -> int:
    """Initialize academic years for a school"""
    current_year = date.today().year
    
    academic_years_data = [
        {
            'name': f'{current_year}-{current_year+1}',
            'start_date': date(current_year, 9, 1),
            'end_date': date(current_year+1, 6, 30),
            'is_active': True,
            'admission_start_date': date(current_year, 1, 1),
            'admission_end_date': date(current_year, 8, 31),
        },
        {
            'name': f'{current_year+1}-{current_year+2}',
            'start_date': date(current_year+1, 9, 1),
            'end_date': date(current_year+2, 6, 30),
            'is_active': True,
            'admission_start_date': date(current_year+1, 1, 1),
            'admission_end_date': date(current_year+1, 8, 31),
        },
    ]
    
    created_count = 0
    for ay_data in academic_years_data:
        academic_year, created = AcademicYear.objects.get_or_create(
            tenant=school,
            name=ay_data['name'],
            defaults=ay_data
        )
        
        if created:
            created_count += 1
            logger.info(f"Created academic year: {academic_year.name} for {school.code}")
    
    return created_count


def _initialize_courses(school: School, create_sample_data: bool) -> int:
    """Initialize courses for a school"""
    if create_sample_data:
        courses_data = [
            {'course_name': 'Nursery', 'code': 'NUR', 'section_name': 'Early Years'},
            {'course_name': 'Reception', 'code': 'REC', 'section_name': 'Early Years'},
            {'course_name': 'Grade 1', 'code': 'G1', 'section_name': 'Primary'},
            {'course_name': 'Grade 2', 'code': 'G2', 'section_name': 'Primary'},
            {'course_name': 'Grade 3', 'code': 'G3', 'section_name': 'Primary'},
            {'course_name': 'Grade 4', 'code': 'G4', 'section_name': 'Primary'},
            {'course_name': 'Grade 5', 'code': 'G5', 'section_name': 'Primary'},
            {'course_name': 'Grade 6', 'code': 'G6', 'section_name': 'Primary'},
            {'course_name': 'Grade 7', 'code': 'G7', 'section_name': 'Primary'},
            {'course_name': 'Grade 8', 'code': 'G8', 'section_name': 'Secondary'},
            {'course_name': 'Grade 9', 'code': 'G9', 'section_name': 'Secondary'},
            {'course_name': 'Grade 10', 'code': 'G10', 'section_name': 'Secondary'},
        ]
    else:
        # Minimal data - just a few basic courses
        courses_data = [
            {'course_name': 'Grade 1', 'code': 'G1', 'section_name': 'Primary'},
            {'course_name': 'Grade 7', 'code': 'G7', 'section_name': 'Primary'},
            {'course_name': 'Grade 8', 'code': 'G8', 'section_name': 'Secondary'},
        ]
    
    created_count = 0
    for course_data in courses_data:
        course, created = Course.objects.get_or_create(
            tenant=school,
            code=course_data['code'],
            defaults={
                'course_name': course_data['course_name'],
                'section_name': course_data['section_name'],
                'is_deleted': False
            }
        )
        
        if created:
            created_count += 1
            logger.info(f"Created course: {course.course_name} for {school.code}")
    
    return created_count


def _initialize_student_categories(school: School, create_sample_data: bool) -> int:
    """Initialize student categories for a school"""
    if create_sample_data:
        categories_data = [
            'Regular Student',
            'International Student',
            'Staff Child',
            'Scholarship Student',
            'Transfer Student',
            'Special Needs Student',
        ]
    else:
        # Minimal data
        categories_data = [
            'Regular Student',
            'International Student',
        ]
    
    created_count = 0
    for category_name in categories_data:
        category, created = StudentCategory.objects.get_or_create(
            tenant=school,
            name=category_name,
            defaults={'is_deleted': False}
        )
        
        if created:
            created_count += 1
            logger.info(f"Created student category: {category.name} for {school.code}")
    
    return created_count


def ensure_basic_data_exists(school: Optional[School] = None):
    """
    Ensure basic data exists for the admission system to function.
    If school is provided, initializes data for that school only.
    If school is None, initializes global data and data for all schools.
    
    This function is safe to call multiple times and during application startup.
    
    Args:
        school: Optional School instance to initialize data for
    
    Returns:
        bool: True if all initialization was successful
    """
    success = True
    
    try:
        # Always ensure countries exist
        if not initialize_countries():
            success = False
        
        if school:
            # Initialize data for specific school
            if not initialize_school_data(school, create_sample_data=False):
                success = False
        else:
            # Initialize data for all schools
            schools = School.objects.all()
            for school_instance in schools:
                if not initialize_school_data(school_instance, create_sample_data=False):
                    success = False
        
        return success
        
    except Exception as e:
        logger.error(f"Error in ensure_basic_data_exists: {str(e)}")
        return False


def check_admission_prerequisites(school: School) -> dict:
    """
    Check if all prerequisites for admission applications exist for a school.
    
    Args:
        school: The School instance to check
    
    Returns:
        dict: Dictionary with check results and missing items
    """
    result = {
        'ready': True,
        'missing': [],
        'warnings': [],
        'counts': {}
    }
    
    try:
        # Check academic years
        active_academic_years = AcademicYear.objects.filter(
            tenant=school, is_active=True
        ).count()
        result['counts']['academic_years'] = active_academic_years
        
        if active_academic_years == 0:
            result['ready'] = False
            result['missing'].append('No active academic years found')
        
        # Check courses
        available_courses = Course.objects.filter(
            tenant=school, is_deleted=False
        ).count()
        result['counts']['courses'] = available_courses
        
        if available_courses == 0:
            result['ready'] = False
            result['missing'].append('No courses available')
        
        # Check student categories
        student_categories = StudentCategory.objects.filter(
            tenant=school, is_deleted=False
        ).count()
        result['counts']['student_categories'] = student_categories
        
        if student_categories == 0:
            result['warnings'].append('No student categories defined')
        
        # Check countries (global)
        countries_count = Country.objects.count()
        result['counts']['countries'] = countries_count
        
        if countries_count == 0:
            result['ready'] = False
            result['missing'].append('No countries available')
        
        return result
        
    except Exception as e:
        logger.error(f"Error checking admission prerequisites for {school.code}: {str(e)}")
        return {
            'ready': False,
            'missing': ['Error checking prerequisites'],
            'warnings': [],
            'counts': {},
            'error': str(e)
        }
import logging
from typing import Dict, Any, List
from datetime import date, datetime
from django.db.models import QuerySet, Q

from core.models import (
    ExtendedAdmissionApplication, 
    AdmissionDocument,
    AcademicYear,
    Course
)
from .base import TenantAwareService
from .exceptions import (
    ValidationException,
    NotFoundException,
    DuplicateException,
    BusinessLogicException
)
from .logging_service import ServiceLogger, logged_operation

logger = logging.getLogger(__name__)


class ExtendedAdmissionService(TenantAwareService[ExtendedAdmissionApplication]):
    def __init__(self, tenant):
        super().__init__(ExtendedAdmissionApplication, tenant)
        self.logger = ServiceLogger('extended_admission', tenant)

    @logged_operation(action='create', resource_type='extended_admission_application', log_result=True)
    def create_application(
        self,
        form_data: Dict[str, Any],
        user=None
    ) -> ExtendedAdmissionApplication:
        try:
            self._validate_create_application_data(form_data)

            application_number = self._generate_application_number()

            academic_year = None
            if form_data.get('academic_year'):
                try:
                    academic_year_id = str(form_data['academic_year']).strip()
                    if academic_year_id:
                        academic_year = AcademicYear.objects.get(
                            id=academic_year_id,
                            tenant=self.tenant,
                            is_active=True
                        )
                except (AcademicYear.DoesNotExist, ValueError, TypeError) as e:
                    logger.error(f"Academic year error: {str(e)}")
                    raise ValidationException("Selected academic year is not available.")

            course_applied = None
            if form_data.get('course_applied'):
                try:
                    course_id = str(form_data['course_applied']).strip()
                    if course_id:
                        course_applied = Course.objects.get(
                            id=course_id,
                            tenant=self.tenant,
                            is_deleted=False
                        )
                except (Course.DoesNotExist, ValueError, TypeError) as e:
                    logger.error(f"Course error: {str(e)}")
                    raise ValidationException("Selected course is not available.")

            prepared_data = self._prepare_application_data(form_data)

            valid_prepared_data = self._filter_valid_model_fields(prepared_data)

            application_data = {
                'application_number': application_number,
                'tenant': self.tenant,
                'status': 'draft',
                'current_step': 1,
                **valid_prepared_data
            }

            if academic_year:
                application_data['academic_year'] = academic_year
            if course_applied:
                application_data['course_applied'] = course_applied

            application = ExtendedAdmissionApplication.objects.create(**application_data)

            self.logger.log_create(
                resource_type='extended_admission_application',
                resource_id=str(application.id),
                user=user,
                details={
                    'application_number': application_number,
                    'student_name': application.full_name,
                    'course': course_applied.course_name if course_applied else None,
                    'academic_year': academic_year.name if academic_year else None
                }
            )

            return application

        except Exception as e:
            logger.error(f"Error creating extended admission application: {str(e)}")
            raise

    @logged_operation(action='update', resource_type='extended_admission_application', log_result=True)
    def update_application(
        self,
        application_id: str,
        form_data: Dict[str, Any],
        user=None
    ) -> ExtendedAdmissionApplication:
        try:
            application = self.get_by_id(application_id)

            if application.status in ['submitted', 'approved', 'rejected']:
                raise BusinessLogicException(
                    f"Cannot update application with status '{application.status}'"
                )

            prepared_data = self._prepare_application_data(form_data)
            valid_data = self._filter_valid_model_fields(prepared_data)

            for field, value in valid_data.items():
                if hasattr(application, field):
                    setattr(application, field, value)

            if form_data.get('academic_year') and form_data['academic_year'] != str(application.academic_year_id or ''):
                try:
                    academic_year = AcademicYear.objects.get(
                        id=form_data['academic_year'],
                        tenant=self.tenant,
                        is_active=True
                    )
                    application.academic_year = academic_year
                except AcademicYear.DoesNotExist:
                    raise ValidationException("Selected academic year is not available.")

            if form_data.get('course_applied') and form_data['course_applied'] != str(application.course_applied_id or ''):
                try:
                    course_applied = Course.objects.get(
                        id=form_data['course_applied'],
                        tenant=self.tenant,
                        is_deleted=False
                    )
                    application.course_applied = course_applied
                except Course.DoesNotExist:
                    raise ValidationException("Selected course is not available.")

            application.save()

            self.logger.log_update(
                resource_type='extended_admission_application',
                resource_id=str(application.id),
                user=user
            )

            return application

        except ExtendedAdmissionApplication.DoesNotExist:
            raise NotFoundException(f"Application with id {application_id} not found")
        except Exception as e:
            logger.error(f"Error updating extended admission application: {str(e)}")
            raise

    def get_application_by_number(self, application_number: str) -> ExtendedAdmissionApplication:
        try:
            return self.get_base_queryset().get(application_number=application_number)
        except ExtendedAdmissionApplication.DoesNotExist:
            raise NotFoundException(
                f"Extended admission application with number '{application_number}' not found"
            )

    def get_applications_by_status(self, status: str) -> QuerySet[ExtendedAdmissionApplication]:
        return self.filter(status=status).order_by('-application_date')

    def get_applications_by_academic_year(self, academic_year_id: str) -> QuerySet[ExtendedAdmissionApplication]:
        return self.filter(academic_year_id=academic_year_id).order_by('-application_date')

    @logged_operation(action='upload_document', resource_type='extended_admission_application', log_result=True)
    def upload_document(
        self,
        application_id: str,
        document_type: str,
        file_data,
        user=None
    ) -> 'AdmissionDocument':
        try:
            application = self.get_by_id(application_id)
            self._validate_document_upload(file_data, document_type)
            existing_doc = AdmissionDocument.objects.filter(
                application=application,
                document_type=document_type
            ).first()

            if existing_doc:
                if existing_doc.file:
                    try:
                        existing_doc.file.delete(save=False)
                    except:
                        pass 
                existing_doc.delete()

            document = AdmissionDocument.objects.create(
                application=application,
                document_type=document_type,
                file=file_data,
                original_filename=file_data.name,
                file_size=file_data.size,
                tenant=self.tenant
            )

            self.logger.log_create(
                resource_type='admission_document',
                resource_id=str(document.id),
                user=user,
                details={
                    'application_number': application.application_number,
                    'document_type': document_type,
                    'filename': file_data.name,
                    'file_size': file_data.size
                }
            )

            return document

        except ExtendedAdmissionApplication.DoesNotExist:
            raise NotFoundException(f"Application with id {application_id} not found")
        except Exception as e:
            logger.error(f"Error uploading document: {str(e)}")
            raise

    @logged_operation(action='submit', resource_type='extended_admission_application', log_result=True)
    def submit_application(
        self,
        application_id: str,
        user=None
    ) -> ExtendedAdmissionApplication:
        try:
            application = self.get_by_id(application_id)

            if application.status == 'submitted':
                raise BusinessLogicException("Application has already been submitted")

            self._validate_complete_application(application)

            application.status = 'submitted'
            application.save()

            self._notify_status_change(application, 'submitted')

            self.logger.log_update(
                resource_type='extended_admission_application',
                resource_id=str(application.id),
                user=user
            )

            return application

        except ExtendedAdmissionApplication.DoesNotExist:
            raise NotFoundException(f"Application with id {application_id} not found")
        except Exception as e:
            logger.error(f"Error submitting application: {str(e)}")
            raise

    @logged_operation(action='approve', resource_type='extended_admission_application', log_result=True)
    def approve_application(
        self,
        application_id: str,
        user=None
    ) -> ExtendedAdmissionApplication:

        try:
            application = self.get_by_id(application_id)

            if application.status != 'submitted':
                raise BusinessLogicException(
                    f"Cannot approve application with status '{application.status}'"
                )

            application.status = 'approved'

            if not application.address_line1:
                application.address_line1 = ''
            if not application.guardian1_mobile:
                application.guardian1_mobile = ''
            if not application.guardian1_email:
                application.guardian1_email = ''
            if not application.nationality:
                application.nationality = ''

            application.save()

            self._notify_status_change(application, 'approved')

            self.logger.log_update(
                resource_type='extended_admission_application',
                resource_id=str(application.id),
                user=user
            )

            return application

        except ExtendedAdmissionApplication.DoesNotExist:
            raise NotFoundException(f"Application with id {application_id} not found")
        except Exception as e:
            logger.error(f"Error approving application: {str(e)}")
            raise

    def _notify_status_change(self, application, new_status: str) -> None:
        """Notify the primary guardian of an admission status change, through
        Notification Control (Configuration → Notification Control).
        Best-effort — never breaks the status transition."""
        try:
            from core.services.notification_service import NotificationService

            phone = getattr(application, 'guardian1_mobile', None)
            email = getattr(application, 'guardian1_email', None)
            if not phone and not email:
                return
            name = " ".join(filter(None, [
                getattr(application, 'first_name', ''),
                getattr(application, 'last_name', ''),
            ])).strip() or "the applicant"
            NotificationService(self.tenant).dispatch(
                "admission_status_change", "guardians",
                [{"id": application.id, "type": "applicant", "phone": phone, "email": email}],
                title=f"Admission update for {name}",
                message=(
                    f"The admission application for {name} "
                    f"(#{application.application_number}) is now: {new_status}."
                ),
            )
        except Exception:
            logger.exception("admission status-change notification failed")

    def get_admission_statistics(self) -> Dict[str, int]:
        from django.db.models import Count, Q

        base_queryset = self.get_base_queryset()

        status_counts = base_queryset.values('status').annotate(count=Count('id')).order_by('status')

        stats = {
            'total': base_queryset.count(),
            'draft': 0,
            'submitted': 0,
            'under_review': 0,
            'approved': 0,
            'rejected': 0,
            'waitlisted': 0,
            'admitted': 0,
        }

        for item in status_counts:
            status = item['status']
            if status in stats:
                stats[status] = item['count']

        return stats

    def _validate_create_application_data(self, form_data: Dict[str, Any]) -> None:
        if 'application_number' in form_data:
            if self.get_base_queryset().filter(
                application_number=form_data['application_number']
            ).exists():
                raise DuplicateException("Application number already exists")

        required_fields = ['first_name', 'last_name']
        for field in required_fields:
            if not form_data.get(field) or not str(form_data[field]).strip():
                raise ValidationException(f"{field.replace('_', ' ').title()} is required")
        
        if form_data.get('academic_year'):
            try:
                from core.models import AcademicYear
                if not AcademicYear.objects.filter(
                    id=form_data['academic_year'],
                    tenant=self.tenant,
                    is_active=True
                ).exists():
                    raise ValidationException("Selected academic year is not available")
            except (ValueError, TypeError):
                raise ValidationException("Invalid academic year format")
        
        if form_data.get('course_applied'):
            try:
                from core.models import Course
                if not Course.objects.filter(
                    id=form_data['course_applied'],
                    tenant=self.tenant,
                    is_deleted=False
                ).exists():
                    raise ValidationException("Selected course is not available")
            except (ValueError, TypeError):
                raise ValidationException("Invalid course format")
        
        if form_data.get('date_of_birth'):
            try:
                from datetime import date, datetime
                
                if isinstance(form_data['date_of_birth'], str):
                    birth_date = datetime.strptime(form_data['date_of_birth'], '%Y-%m-%d').date()
                elif isinstance(form_data['date_of_birth'], datetime):
                    birth_date = form_data['date_of_birth'].date()
                else:
                    birth_date = form_data['date_of_birth']
                
                today = date.today()
                age = today.year - birth_date.year - ((today.month, today.day) < (birth_date.month, birth_date.day))
                
                if age < 3:
                    raise ValidationException("Student must be at least 3 years old")
                if age > 25:
                    raise ValidationException("Student must be under 25 years old")
                
                if birth_date > today:
                    raise ValidationException("Date of birth cannot be in the future")
                    
            except (ValueError, TypeError) as e:
                raise ValidationException("Invalid date of birth format")

    def _validate_complete_application(self, application: ExtendedAdmissionApplication) -> None:
        required_fields_mapping = {
            "academic_year": application.academic_year,
            "course_applied": application.course_applied,
            "first_name": application.first_name,
            "last_name": application.last_name,
            "date_of_birth": application.date_of_birth,
            "gender": application.gender,
            "nationality": application.nationality,
            "address_line1": application.address_line1,
            "city": application.city,
            "country": application.country,
            "guardian1_first_name": application.guardian1_first_name,
            "guardian1_last_name": application.guardian1_last_name,
            "guardian1_relation": application.guardian1_relation,
            "guardian1_mobile": application.guardian1_mobile,
            "terms_agreement": application.terms_agreement,
            "declaration_agreement": application.declaration_agreement,
            "declaration_date": application.declaration_date,
        }

        missing_fields = []
        for field_name, field_value in required_fields_mapping.items():
            if not field_value or (isinstance(field_value, str) and not field_value.strip()):
                missing_fields.append(field_name)

        if missing_fields:
            raise ValidationException(
                f"Cannot submit application. Missing required fields: {', '.join(missing_fields)}"
            )

        if not application.academic_year:
            raise ValidationException("Academic year is required for submission")

        if not application.course_applied:
            raise ValidationException("Course applied is required for submission")

        if not application.terms_agreement:
            raise ValidationException("Terms and conditions agreement is required for submission")
        
        if not application.declaration_agreement:
            raise ValidationException("Declaration agreement is required for submission")

    def _get_missing_fields(self, form_data: Dict[str, Any], required_fields: List[str]) -> List[str]:
        missing_fields = []

        for field in required_fields:
            value = form_data.get(field)
            if not value or (isinstance(value, str) and not value.strip()):
                missing_fields.append(field)

        return missing_fields

    def _is_required_document(self, document_type: str) -> bool:
        return False

    def _validate_document_upload(self, file_data, document_type: str) -> None:
        max_size = 5 * 1024 * 1024  
        if file_data.size > max_size:
            raise ValidationException("File size exceeds 5MB limit")

        allowed_extensions = ['pdf', 'jpg', 'jpeg', 'png']
        file_extension = file_data.name.split('.')[-1].lower()
        if file_extension not in allowed_extensions:
            raise ValidationException(f"File type '{file_extension}' not allowed. Allowed types: {', '.join(allowed_extensions)}")

    def _prepare_application_data(self, form_data: Dict[str, Any]) -> Dict[str, Any]:
        prepared_data = self._clean_form_data(form_data)

        optional_string_fields_with_defaults = {
            'guardian1_last_name': '',
            'guardian1_occupation': '',
            'guardian1_office_address_line1': '',
            'guardian1_office_city': '',  
            'guardian1_office_phone1': '',
            'guardian1_email': '',
            'guardian2_first_name': '',
            'guardian2_last_name': '',
            'guardian2_relation': '',
            'guardian2_occupation': '',
            'guardian2_office_address_line1': '',
            'guardian2_office_city': '',  
            'guardian2_office_phone1': '',
            'guardian2_mobile': '',
            'guardian2_email': '',
            'religion': '',
            'birth_place': '',
            'mother_tongue': '',
            'previous_school_address': '',
            'previous_school_phone': '',
            'previous_school_email': '',
            'medical_details': '',
            'religious_observances': '',
            'background_information': '',
            'email': '',
            'phone': '',
            'mobile': '',
            'city': '',
        }

        optional_boolean_fields_with_defaults = {
            'has_medical_problems': False,
            'recent_hospitalization': False,
            'has_allergies': False,
        }

        optional_nullable_fields = [
            'expected_start_date', 
            'declaration_date'
        ]

        for field, default_value in optional_string_fields_with_defaults.items():
            if field not in prepared_data or not prepared_data[field]:
                prepared_data[field] = default_value

        for field, default_value in optional_boolean_fields_with_defaults.items():
            if field not in prepared_data:
                prepared_data[field] = default_value

        for field in optional_nullable_fields:
            if field not in prepared_data or not prepared_data[field]:
                prepared_data[field] = None

        fk_fields_to_check = ['country', 'student_category']
        for field in fk_fields_to_check:
            if field in prepared_data and prepared_data[field] == '':
                del prepared_data[field]

        return prepared_data

    def _filter_valid_model_fields(self, data: Dict[str, Any]) -> Dict[str, Any]:
        from core.models import ExtendedAdmissionApplication

        model_fields = set(field.name for field in ExtendedAdmissionApplication._meta.get_fields())

        valid_data = {}
        for key, value in data.items():
            if key in model_fields:
                valid_data[key] = value
            else:
                logger.warning(f"Skipping invalid field '{key}' - not found in ExtendedAdmissionApplication model")

        return valid_data

    def _clean_form_data(self, form_data: Dict[str, Any]) -> Dict[str, Any]:
        field_mapping = {
            'guardian1_city': 'guardian1_office_city',
            'guardian2_city': 'guardian2_office_city',
        }

        mapped_form_data = {}
        for key, value in form_data.items():
            mapped_key = field_mapping.get(key, key)  
            mapped_form_data[mapped_key] = value

        cleaned_data = {}

        string_fields = [
            'first_name', 'middle_name', 'last_name', 'gender', 'nationality',
            'religion', 'birth_place', 'mother_tongue', 'email',
            'address', 'address_line1', 'address_line2', 'city',
            'phone', 'mobile',
            'guardian1_first_name', 'guardian1_last_name', 'guardian1_relation',
            'guardian1_occupation', 'guardian1_office_address_line1', 
            'guardian1_office_city', 'guardian1_office_phone1', 'guardian1_mobile', 'guardian1_email',
            'guardian2_first_name', 'guardian2_last_name', 'guardian2_relation',
            'guardian2_occupation', 'guardian2_office_address_line1', 
            'guardian2_office_city', 'guardian2_office_phone1', 'guardian2_mobile', 'guardian2_email',
            'previous_school_name', 'previous_school_address', 
            'previous_school_phone', 'previous_school_email',
            'medical_details', 'religious_observances', 'background_information'
        ]

        for field in string_fields:
            if field in mapped_form_data and mapped_form_data[field]:
                cleaned_data[field] = str(mapped_form_data[field]).strip()

        if 'country' in mapped_form_data and mapped_form_data['country']:
            country_value = str(mapped_form_data['country']).strip()
            if country_value and country_value != 'null' and country_value != '':
                try:
                    from core.models import Country
                    country_obj = Country.objects.filter(name__iexact=country_value).first()
                    
                    if not country_obj:
                        country_obj = Country.objects.filter(code__iexact=country_value).first()
                    
                    if country_obj:
                        cleaned_data['country'] = country_obj
                    else:
                        country_obj = Country.objects.create(name=country_value)
                        cleaned_data['country'] = country_obj
                        logger.info(f"Created new country: {country_value}")
                except Exception as e:
                    logger.warning(f"Failed to handle country '{country_value}': {str(e)}")
                    cleaned_data['country'] = None

        if 'student_category' in mapped_form_data and mapped_form_data['student_category']:
            category_value = str(mapped_form_data['student_category']).strip()
            if category_value:
                try:
                    from core.models import StudentCategory
                    category_obj = StudentCategory.objects.filter(
                        tenant=self.tenant,
                        name__iexact=category_value,
                        is_deleted=False
                    ).first()

                    if category_obj:
                        cleaned_data['student_category'] = category_obj
                    else:
                        category_obj = StudentCategory.objects.create(
                            tenant=self.tenant,
                            name=category_value
                        )
                        cleaned_data['student_category'] = category_obj
                        logger.info(f"Created new student category: {category_value}")
                except Exception as e:
                    logger.warning(f"Failed to handle student_category '{category_value}': {str(e)}")

        boolean_fields = [
            'terms_agreement', 'declaration_agreement',
            'has_medical_problems', 'recent_hospitalization',
            'has_allergies'
        ]

        for field in boolean_fields:
            if field in mapped_form_data:
                cleaned_data[field] = bool(mapped_form_data[field])

        date_fields = ['date_of_birth', 'expected_start_date', 'declaration_date']

        for field in date_fields:
            if field in mapped_form_data and mapped_form_data[field]:
                if isinstance(mapped_form_data[field], str):
                    try:
                        cleaned_data[field] = datetime.strptime(mapped_form_data[field], '%Y-%m-%d').date()
                    except ValueError:
                        logger.warning(f"Invalid date format for {field}: {mapped_form_data[field]}")
                elif isinstance(mapped_form_data[field], date):
                    cleaned_data[field] = mapped_form_data[field]

        return cleaned_data

    def _generate_application_number(self) -> str:
        from datetime import datetime
        import random
        import string

        year = datetime.now().year

        while True:
            random_part = ''.join(random.choices(string.digits, k=6))
            application_number = f"APP-{year}-{random_part}"

            if not self.get_base_queryset().filter(
                application_number=application_number
            ).exists():
                return application_number

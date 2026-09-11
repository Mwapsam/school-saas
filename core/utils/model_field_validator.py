"""
Model Field Validator Utility

This utility helps prevent field mismatch errors by validating model attributes
before they're used in code, especially for integrations like QuickBooks sync.
"""

import logging
from typing import Dict, List, Optional, Any
from django.db import models

logger = logging.getLogger(__name__)


class ModelFieldValidator:
    """
    Utility class to validate model fields and provide safe access to model attributes.
    """
    
    def __init__(self):
        self._field_cache = {}
    
    def get_model_fields(self, model_class) -> Dict[str, models.Field]:
        """
        Get all fields for a Django model class.
        
        Args:
            model_class: Django model class
            
        Returns:
            Dict mapping field names to field objects
        """
        cache_key = f"{model_class.__module__}.{model_class.__name__}"
        
        if cache_key not in self._field_cache:
            fields = {}
            for field in model_class._meta.get_fields():
                if hasattr(field, 'name'):
                    fields[field.name] = field
            self._field_cache[cache_key] = fields
            
        return self._field_cache[cache_key]
    
    def validate_field_exists(self, model_class, field_name: str) -> bool:
        """
        Check if a field exists on a model.
        
        Args:
            model_class: Django model class
            field_name: Name of the field to check
            
        Returns:
            True if field exists, False otherwise
        """
        fields = self.get_model_fields(model_class)
        return field_name in fields
    
    def validate_fields_exist(self, model_class, field_names: List[str]) -> Dict[str, bool]:
        """
        Check if multiple fields exist on a model.
        
        Args:
            model_class: Django model class
            field_names: List of field names to check
            
        Returns:
            Dict mapping field names to their existence status
        """
        fields = self.get_model_fields(model_class)
        return {field_name: field_name in fields for field_name in field_names}
    
    def get_safe_field_value(self, model_instance, field_name: str, default=None) -> Any:
        """
        Safely get a field value from a model instance.
        
        Args:
            model_instance: Instance of a Django model
            field_name: Name of the field to get
            default: Default value if field doesn't exist or is None
            
        Returns:
            Field value or default
        """
        try:
            if hasattr(model_instance, field_name):
                value = getattr(model_instance, field_name)
                return value if value is not None else default
            else:
                logger.warning(f"Field '{field_name}' does not exist on {model_instance.__class__.__name__}")
                return default
        except Exception as e:
            logger.error(f"Error accessing field '{field_name}' on {model_instance.__class__.__name__}: {str(e)}")
            return default
    
    def get_field_alternatives(self, model_class, preferred_field: str, alternative_fields: List[str]) -> Optional[str]:
        """
        Find the first available field from a list of alternatives.
        
        Args:
            model_class: Django model class
            preferred_field: Preferred field name
            alternative_fields: List of alternative field names
            
        Returns:
            First available field name, or None if none exist
        """
        # Check preferred field first
        if self.validate_field_exists(model_class, preferred_field):
            return preferred_field
            
        # Check alternatives
        for field_name in alternative_fields:
            if self.validate_field_exists(model_class, field_name):
                return field_name
                
        return None
    
    def create_field_mapping_report(self, model_class) -> str:
        """
        Create a detailed report of all fields in a model.
        
        Args:
            model_class: Django model class
            
        Returns:
            Formatted string report of all fields
        """
        fields = self.get_model_fields(model_class)
        
        report_lines = [
            f"=== {model_class.__name__} Field Report ===",
            f"Total fields: {len(fields)}",
            ""
        ]
        
        for field_name, field in fields.items():
            field_type = field.__class__.__name__
            is_required = not (getattr(field, 'null', False) or getattr(field, 'blank', False))
            max_length = getattr(field, 'max_length', None)
            
            field_info = f"{field_name:<25} | {field_type:<20} | Required: {is_required:<5}"
            if max_length:
                field_info += f" | Max Length: {max_length}"
                
            report_lines.append(field_info)
        
        return "\n".join(report_lines)


# Pre-defined field mappings for common models
STUDENT_FIELD_MAPPINGS = {
    # Contact Information
    'phone': ['phone1', 'phone2'],
    'mobile': ['phone1', 'phone2'], 
    'mobile_number': ['phone1', 'phone2'],
    'primary_phone': ['phone1', 'phone2'],
    
    # Address Information  
    'address': ['address_line1', 'address_line2'],
    'street_address': ['address_line1'],
    'postal_code': ['pin_code'],
    'zip_code': ['pin_code'],
    
    # Personal Information
    'full_name': ['first_name', 'last_name'],
    'display_name': ['first_name', 'last_name'],
    
    # Status
    'active': ['is_active'],
    'deleted': ['is_deleted'],
}

GUARDIAN_FIELD_MAPPINGS = {
    # Contact Information
    'phone': ['mobile_phone', 'office_phone'],
    'mobile': ['mobile_phone'],
    'mobile_number': ['mobile_phone'],
    'office': ['office_phone'],
    
    # Address Information
    'address': ['office_address_line1', 'office_address_line2'],
    'office_address': ['office_address_line1', 'office_address_line2'],
    
    # Personal Information
    'date_of_birth': ['dob'],
    'full_name': ['first_name', 'last_name'],
}


class StudentFieldHelper:
    """Helper class specifically for Student model field access"""
    
    def __init__(self):
        self.validator = ModelFieldValidator()
        
    def get_phone_number(self, student) -> Optional[str]:
        """Get student's phone number (phone1 or phone2)"""
        phone1 = self.validator.get_safe_field_value(student, 'phone1')
        if phone1:
            return phone1
        return self.validator.get_safe_field_value(student, 'phone2')
    
    def get_full_address(self, student) -> Dict[str, Optional[str]]:
        """Get student's full address information"""
        return {
            'address_line1': self.validator.get_safe_field_value(student, 'address_line1'),
            'address_line2': self.validator.get_safe_field_value(student, 'address_line2'), 
            'city': self.validator.get_safe_field_value(student, 'city'),
            'state': self.validator.get_safe_field_value(student, 'state'),
            'postal_code': self.validator.get_safe_field_value(student, 'pin_code'),
            'country': self.validator.get_safe_field_value(student, 'country'),
        }
    
    def get_display_name(self, student) -> str:
        """Get student's display name"""
        first_name = self.validator.get_safe_field_value(student, 'first_name', 'Unknown')
        middle_name = self.validator.get_safe_field_value(student, 'middle_name', '')
        last_name = self.validator.get_safe_field_value(student, 'last_name', '')
        
        name_parts = [first_name]
        if middle_name:
            name_parts.append(middle_name)
        if last_name:
            name_parts.append(last_name)
            
        return ' '.join(name_parts)
    
    def get_display_name_with_id(self, student) -> str:
        """Get student's display name with admission number"""
        display_name = self.get_display_name(student)
        admission_no = self.validator.get_safe_field_value(student, 'admission_no')
        
        if admission_no:
            return f"{display_name} ({admission_no})"
        return display_name
    
    def validate_required_fields_for_quickbooks(self, student) -> Dict[str, Any]:
        """Validate student has required fields for QuickBooks sync"""
        required_checks = {
            'has_first_name': bool(self.validator.get_safe_field_value(student, 'first_name')),
            'has_last_name': bool(self.validator.get_safe_field_value(student, 'last_name')),
            'has_admission_no': bool(self.validator.get_safe_field_value(student, 'admission_no')),
            'has_email': bool(self.validator.get_safe_field_value(student, 'email')),
            'has_phone': bool(self.get_phone_number(student)),
            'has_address': bool(
                self.validator.get_safe_field_value(student, 'address_line1') or
                self.validator.get_safe_field_value(student, 'city')
            ),
            'is_active': self.validator.get_safe_field_value(student, 'is_active', False),
            'is_deleted': self.validator.get_safe_field_value(student, 'is_deleted', True),
        }
        
        required_checks['is_ready_for_sync'] = (
            required_checks['has_first_name'] and 
            required_checks['has_last_name'] and
            required_checks['has_admission_no'] and
            required_checks['is_active'] and
            not required_checks['is_deleted']
        )
        
        return required_checks


class GuardianFieldHelper:
    """Helper class specifically for Guardian model field access (used by
    guardian-centric QuickBooks customer sync)."""

    def __init__(self):
        self.validator = ModelFieldValidator()

    def get_phone_number(self, guardian) -> Optional[str]:
        mobile = self.validator.get_safe_field_value(guardian, 'mobile_phone')
        if mobile:
            return mobile
        return self.validator.get_safe_field_value(guardian, 'office_phone')

    def get_full_address(self, guardian) -> Dict[str, Optional[str]]:
        return {
            'address_line1': self.validator.get_safe_field_value(guardian, 'office_address_line1'),
            'address_line2': self.validator.get_safe_field_value(guardian, 'office_address_line2'),
            'city': self.validator.get_safe_field_value(guardian, 'city'),
            'state': self.validator.get_safe_field_value(guardian, 'state'),
            'postal_code': None,
            'country': self.validator.get_safe_field_value(guardian, 'country'),
        }

    def get_display_name(self, guardian) -> str:
        first_name = self.validator.get_safe_field_value(guardian, 'first_name', 'Unknown')
        last_name = self.validator.get_safe_field_value(guardian, 'last_name', '')
        return ' '.join(p for p in [first_name, last_name] if p)

    def get_display_name_with_id(self, guardian) -> str:
        """Display name with a short guardian id suffix, guaranteeing
        uniqueness in QuickBooks (guardians have no admission_no)."""
        display_name = self.get_display_name(guardian)
        short_id = str(getattr(guardian, 'id', ''))[:8]
        return f"{display_name} (G-{short_id})" if short_id else display_name

    def validate_required_fields_for_quickbooks(self, guardian) -> Dict[str, Any]:
        required_checks = {
            'has_first_name': bool(self.validator.get_safe_field_value(guardian, 'first_name')),
            'has_last_name': bool(self.validator.get_safe_field_value(guardian, 'last_name')),
            'has_email': bool(self.validator.get_safe_field_value(guardian, 'email')),
            'has_phone': bool(self.get_phone_number(guardian)),
            'is_active': self.validator.get_safe_field_value(guardian, 'is_active', False),
        }
        required_checks['is_ready_for_sync'] = (
            required_checks['has_first_name'] and required_checks['is_active']
        )
        return required_checks


guardian_field_helper = GuardianFieldHelper()


def validate_guardian_fields_for_quickbooks(guardian) -> bool:
    """Quick validation: is this guardian ready to sync as a QB customer."""
    return guardian_field_helper.validate_required_fields_for_quickbooks(guardian)['is_ready_for_sync']


def get_guardian_quickbooks_data(guardian) -> Dict[str, Any]:
    """Extract all relevant data from a Guardian instance for QuickBooks sync."""
    helper = guardian_field_helper
    validator = model_field_validator

    address_info = helper.get_full_address(guardian)

    return {
        'display_name': helper.get_display_name(guardian),
        'display_name_with_id': helper.get_display_name_with_id(guardian),
        'first_name': validator.get_safe_field_value(guardian, 'first_name', ''),
        'last_name': validator.get_safe_field_value(guardian, 'last_name', ''),

        'email': validator.get_safe_field_value(guardian, 'email'),
        'phone': helper.get_phone_number(guardian),

        'address_line1': address_info['address_line1'],
        'address_line2': address_info['address_line2'],
        'city': address_info['city'],
        'state': address_info['state'],
        'postal_code': address_info['postal_code'],
        'country': address_info['country'],

        'is_active': validator.get_safe_field_value(guardian, 'is_active', False),

        'validation_results': helper.validate_required_fields_for_quickbooks(guardian),
        'is_ready_for_sync': validate_guardian_fields_for_quickbooks(guardian),
    }


# Global instances for easy access
model_field_validator = ModelFieldValidator()
student_field_helper = StudentFieldHelper()


def validate_student_fields_for_quickbooks(student) -> bool:
    """
    Quick validation function to check if a student is ready for QuickBooks sync.
    
    Args:
        student: Student model instance
        
    Returns:
        True if student has required fields for sync, False otherwise
    """
    validation_result = student_field_helper.validate_required_fields_for_quickbooks(student)
    return validation_result['is_ready_for_sync']


def get_student_quickbooks_data(student) -> Dict[str, Any]:
    """
    Extract all relevant data from a Student instance for QuickBooks sync.
    
    Args:
        student: Student model instance
        
    Returns:
        Dict with all QuickBooks-relevant student data
    """
    helper = student_field_helper
    validator = model_field_validator
    
    address_info = helper.get_full_address(student)
    
    return {
        # Basic Information
        'display_name': helper.get_display_name(student),
        'display_name_with_id': helper.get_display_name_with_id(student),
        'first_name': validator.get_safe_field_value(student, 'first_name', ''),
        'middle_name': validator.get_safe_field_value(student, 'middle_name', ''),
        'last_name': validator.get_safe_field_value(student, 'last_name', ''),
        'admission_no': validator.get_safe_field_value(student, 'admission_no', ''),
        
        # Contact Information
        'email': validator.get_safe_field_value(student, 'email'),
        'phone': helper.get_phone_number(student),
        'phone1': validator.get_safe_field_value(student, 'phone1'),
        'phone2': validator.get_safe_field_value(student, 'phone2'),
        
        # Address Information
        'address_line1': address_info['address_line1'],
        'address_line2': address_info['address_line2'],
        'city': address_info['city'],
        'state': address_info['state'],
        'postal_code': address_info['postal_code'],
        'country': address_info['country'],
        
        # Status Information
        'is_active': validator.get_safe_field_value(student, 'is_active', False),
        'is_deleted': validator.get_safe_field_value(student, 'is_deleted', True),
        
        # Validation
        'validation_results': helper.validate_required_fields_for_quickbooks(student),
        'is_ready_for_sync': validate_student_fields_for_quickbooks(student),
    }
from django import forms
from django.contrib.auth.forms import AuthenticationForm
from django.core.exceptions import ValidationError
from datetime import date
from .models import (
    Course, AdmissionApplication, ApplicantEnquiry, ApplicantEnquiryStage,
    AcademicYear, Employee, EnquiryFollowUp, EnquiryStageLogNote
)


class StaffOnlyAuthenticationForm(AuthenticationForm):
    """Rejects login for accounts without dashboard access (`is_admin=False`).

    Teachers and parents are provisioned as portal-only accounts
    (core.services.portal_account_service) and must use the separate
    Next.js portal instead of this server-rendered dashboard.
    """

    def confirm_login_allowed(self, user):
        super().confirm_login_allowed(user)
        if not getattr(user, "is_admin", False):
            raise ValidationError(
                "This account cannot access the staff dashboard. "
                "Please use the Parent & Teacher Portal to log in.",
                code="not_staff",
            )


class AdmissionApplicationForm(forms.ModelForm):
    """Form for creating admission applications."""
    
    class Meta:
        model = AdmissionApplication
        fields = [
            'first_name', 'middle_name', 'last_name', 'date_of_birth', 
            'gender', 'course_applied', 'guardian_name', 'guardian_phone', 
            'guardian_email', 'address'
        ]
        widgets = {
            'first_name': forms.TextInput(attrs={
                'class': 'form-control',
                'placeholder': 'Enter first name',
                'required': True
            }),
            'middle_name': forms.TextInput(attrs={
                'class': 'form-control',
                'placeholder': 'Enter middle name (optional)'
            }),
            'last_name': forms.TextInput(attrs={
                'class': 'form-control',
                'placeholder': 'Enter last name',
                'required': True
            }),
            'date_of_birth': forms.DateInput(attrs={
                'class': 'form-control',
                'type': 'date',
                'required': True
            }),
            'gender': forms.Select(attrs={
                'class': 'form-control',
                'required': True
            }),
            'course_applied': forms.Select(attrs={
                'class': 'form-control',
                'required': True
            }),
            'guardian_name': forms.TextInput(attrs={
                'class': 'form-control',
                'placeholder': 'Enter guardian/parent name',
                'required': True
            }),
            'guardian_phone': forms.TextInput(attrs={
                'class': 'form-control',
                'placeholder': 'Enter guardian phone number',
                'required': True
            }),
            'guardian_email': forms.EmailInput(attrs={
                'class': 'form-control',
                'placeholder': 'Enter guardian email (optional)'
            }),
            'address': forms.Textarea(attrs={
                'class': 'form-control',
                'rows': 3,
                'placeholder': 'Enter full address',
                'required': True
            })
        }

    def __init__(self, *args, **kwargs):
        school = kwargs.pop('school', None)
        super().__init__(*args, **kwargs)
        
        # Filter courses by school
        if school:
            self.fields['course_applied'].queryset = Course.objects.filter(
                is_deleted=False
            )
        
        # Set gender choices
        self.fields['gender'].choices = [
            ('', 'Select Gender'),
            ('male', 'Male'),
            ('female', 'Female'),
            ('other', 'Other')
        ]

    def clean_date_of_birth(self):
        """Validate date of birth is in the past."""
        dob = self.cleaned_data.get('date_of_birth')
        if dob and dob >= date.today():
            raise ValidationError("Date of birth must be in the past.")
        return dob

    def clean_guardian_phone(self):
        """Basic phone number validation."""
        phone = self.cleaned_data.get('guardian_phone')
        if phone:
            # Remove spaces and common separators
            phone = phone.replace(' ', '').replace('-', '').replace('(', '').replace(')', '')
            if not phone.isdigit() or len(phone) < 9:
                raise ValidationError("Please enter a valid phone number.")
        return phone


class AdmissionReviewForm(forms.Form):
    """Form for reviewing admission applications."""
    
    action = forms.ChoiceField(
        choices=[
            ('approve', 'Approve'),
            ('reject', 'Reject')
        ],
        widget=forms.RadioSelect(attrs={'class': 'form-check-input'})
    )
    
    admission_no = forms.CharField(
        max_length=20,
        required=False,
        widget=forms.TextInput(attrs={
            'class': 'form-control',
            'placeholder': 'Auto-generated if left blank'
        }),
        help_text="Leave blank to auto-generate admission number"
    )
    
    remarks = forms.CharField(
        widget=forms.Textarea(attrs={
            'class': 'form-control',
            'rows': 4,
            'placeholder': 'Enter remarks or reason for decision'
        }),
        required=True
    )

    def clean(self):
        """Validate form based on action selected."""
        cleaned_data = super().clean()
        action = cleaned_data.get('action')
        remarks = cleaned_data.get('remarks')
        
        if action == 'reject' and not remarks:
            raise ValidationError("Remarks are required when rejecting an application.")
        
        return cleaned_data


class AdmissionSearchForm(forms.Form):
    """Form for searching admission applications."""
    
    query = forms.CharField(
        max_length=100,
        required=False,
        widget=forms.TextInput(attrs={
            'class': 'form-control',
            'placeholder': 'Search by name, application number, or guardian...'
        })
    )
    
    status = forms.ChoiceField(
        choices=[
            ('', 'All Status'),
            ('pending', 'Pending'),
            ('approved', 'Approved'),
            ('rejected', 'Rejected')
        ],
        required=False,
        widget=forms.Select(attrs={'class': 'form-control'})
    )
    
    course = forms.ModelChoiceField(
        queryset=Course.objects.none(),
        required=False,
        empty_label="All Courses",
        widget=forms.Select(attrs={'class': 'form-control'})
    )

    def __init__(self, *args, **kwargs):
        school = kwargs.pop('school', None)
        super().__init__(*args, **kwargs)
        
        if school:
            self.fields['course'].queryset = Course.objects.filter(
                is_deleted=False
            )


# ========================================
# ENQUIRY MANAGEMENT FORMS
# ========================================

class ApplicantEnquiryForm(forms.ModelForm):
    """Form for creating and updating applicant enquiries"""

    class Meta:
        model = ApplicantEnquiry
        fields = [
            # Student Information
            'first_name', 'last_name', 'date_of_birth',
            # Academic Information
            'course', 'academic_year',
            # Guardian Information
            'guardian_first_name', 'guardian_last_name', 'guardian_address_line1',
            'guardian_address_line2', 'guardian_relation', 'guardian_phone', 'guardian_email'
        ]
        widgets = {
            # Student Information
            'first_name': forms.TextInput(attrs={
                'class': 'form-control',
                'placeholder': 'Enter first name',
                'required': True
            }),
            'last_name': forms.TextInput(attrs={
                'class': 'form-control',
                'placeholder': 'Enter last name',
                'required': True
            }),
            'date_of_birth': forms.DateInput(attrs={
                'class': 'form-control',
                'type': 'date'
            }),
            # Academic Information
            'course': forms.Select(attrs={
                'class': 'form-select',
                'required': True
            }),
            'academic_year': forms.Select(attrs={
                'class': 'form-select',
                'required': True
            }),
            # Guardian Information
            'guardian_first_name': forms.TextInput(attrs={
                'class': 'form-control',
                'placeholder': 'Enter guardian first name'
            }),
            'guardian_last_name': forms.TextInput(attrs={
                'class': 'form-control',
                'placeholder': 'Enter guardian last name'
            }),
            'guardian_address_line1': forms.TextInput(attrs={
                'class': 'form-control',
                'placeholder': 'Enter guardian address line 1'
            }),
            'guardian_address_line2': forms.TextInput(attrs={
                'class': 'form-control',
                'placeholder': 'Enter guardian address line 2'
            }),
            'guardian_relation': forms.TextInput(attrs={
                'class': 'form-control',
                'placeholder': 'Enter relation (e.g., Father, Mother)'
            }),
            'guardian_phone': forms.TextInput(attrs={
                'class': 'form-control',
                'placeholder': 'Enter guardian mobile phone'
            }),
            'guardian_email': forms.EmailInput(attrs={
                'class': 'form-control',
                'placeholder': 'Enter guardian email'
            }),
        }

    def __init__(self, *args, **kwargs):
        tenant = kwargs.pop('tenant', None)
        super().__init__(*args, **kwargs)

        if tenant:
            # Filter querysets by tenant
            self.fields['course'].queryset = Course.objects.filter(tenant=tenant, is_deleted=False)

            # Include current and upcoming academic years (not just active ones)
            from django.utils import timezone
            from django.db.models import Q
            today = timezone.now().date()

            self.fields['academic_year'].queryset = AcademicYear.objects.filter(
                tenant=tenant
            ).filter(
                # Include years that are either:
                # 1. Currently active (is_active=True)
                # 2. Starting in the future (upcoming years)
                Q(is_active=True) |
                Q(start_date__gt=today)
            ).order_by('start_date')

        # Make certain fields required
        self.fields['first_name'].required = True
        self.fields['last_name'].required = True
        self.fields['course'].required = True
        self.fields['academic_year'].required = True

    def clean_guardian_phone(self):
        phone = self.cleaned_data.get('guardian_phone')
        if phone:
            # Basic phone number validation
            import re
            if not re.match(r'^[\d\s\+\-\(\)]+$', phone):
                raise ValidationError('Enter a valid phone number.')
        return phone


class EnquiryFilterForm(forms.Form):
    """Form for filtering enquiry listings"""

    search = forms.CharField(
        required=False,
        widget=forms.TextInput(attrs={
            'class': 'form-control',
            'placeholder': 'Search by name, email, phone, or enquiry number...',
        })
    )

    stage = forms.ModelChoiceField(
        queryset=ApplicantEnquiryStage.objects.none(),
        required=False,
        empty_label="All Stages",
        widget=forms.Select(attrs={'class': 'form-select'})
    )

    course = forms.ModelChoiceField(
        queryset=Course.objects.none(),
        required=False,
        empty_label="All Courses",
        widget=forms.Select(attrs={'class': 'form-select'})
    )

    academic_year = forms.ModelChoiceField(
        queryset=AcademicYear.objects.none(),
        required=False,
        empty_label="All Academic Years",
        widget=forms.Select(attrs={'class': 'form-select'})
    )

    is_processed = forms.ChoiceField(
        choices=[
            ('', 'All'),
            ('true', 'Processed'),
            ('false', 'Not Processed'),
        ],
        required=False,
        widget=forms.Select(attrs={'class': 'form-select'})
    )

    date_from = forms.DateField(
        required=False,
        widget=forms.DateInput(attrs={'class': 'form-control', 'type': 'date'})
    )

    date_to = forms.DateField(
        required=False,
        widget=forms.DateInput(attrs={'class': 'form-control', 'type': 'date'})
    )

    def __init__(self, *args, **kwargs):
        tenant = kwargs.pop('tenant', None)
        super().__init__(*args, **kwargs)

        if tenant:
            self.fields['stage'].queryset = ApplicantEnquiryStage.objects.filter(
                tenant=tenant
            )
            self.fields['course'].queryset = Course.objects.filter(
                tenant=tenant, is_deleted=False
            )

            # Include current and upcoming academic years for filtering
            from django.utils import timezone
            from django.db.models import Q
            today = timezone.now().date()

            self.fields['academic_year'].queryset = AcademicYear.objects.filter(
                tenant=tenant
            ).filter(
                Q(is_active=True) |
                Q(start_date__gt=today)
            ).order_by('start_date')


class EnquiryBulkActionForm(forms.Form):
    """Form for bulk actions on enquiries"""

    ACTION_CHOICES = [
        ('', 'Select Action'),
        ('delete', 'Delete Selected'),
        ('mark_processed', 'Mark as Processed'),
        ('mark_unprocessed', 'Mark as Not Processed'),
        ('export', 'Export Selected'),
    ]

    action = forms.ChoiceField(
        choices=ACTION_CHOICES,
        required=True,
        widget=forms.Select(attrs={'class': 'form-select'})
    )

    enquiry_ids = forms.CharField(
        widget=forms.HiddenInput(),
        required=False
    )

    def __init__(self, *args, **kwargs):
        # Remove tenant parameter if provided (not needed for this form)
        kwargs.pop('tenant', None)
        super().__init__(*args, **kwargs)

    def clean_enquiry_ids(self):
        ids_str = self.cleaned_data.get('enquiry_ids', '')
        if not ids_str:
            raise ValidationError('No enquiries selected.')

        try:
            # Convert comma-separated string to list of UUIDs
            ids = [id.strip() for id in ids_str.split(',') if id.strip()]
            return ids
        except:
            raise ValidationError('Invalid enquiry IDs.')


class EnquiryFollowUpForm(forms.ModelForm):
    """Form for adding follow-ups to enquiries"""

    class Meta:
        model = EnquiryFollowUp
        fields = ['follow_up_type', 'scheduled_date', 'assigned_to', 'notes']
        widgets = {
            'follow_up_type': forms.Select(attrs={'class': 'form-select'}),
            'scheduled_date': forms.DateTimeInput(attrs={
                'class': 'form-control',
                'type': 'datetime-local'
            }),
            'assigned_to': forms.Select(attrs={'class': 'form-select'}),
            'notes': forms.Textarea(attrs={
                'class': 'form-control',
                'rows': 3,
                'placeholder': 'Enter follow-up notes'
            }),
        }

    def __init__(self, *args, **kwargs):
        tenant = kwargs.pop('tenant', None)
        super().__init__(*args, **kwargs)

        if tenant:
            self.fields['assigned_to'].queryset = Employee.objects.filter(
                tenant=tenant,
                user__is_active=True
            )

        # Make certain fields required
        self.fields['follow_up_type'].required = True
        self.fields['scheduled_date'].required = True


class EnquiryStageLogNoteForm(forms.ModelForm):
    """Form for adding notes to stage logs"""

    class Meta:
        model = EnquiryStageLogNote
        fields = ['notes', 'follow_up_date']
        widgets = {
            'notes': forms.Textarea(attrs={
                'class': 'form-control',
                'rows': 3,
                'placeholder': 'Enter your note...',
                'required': True
            }),
            'follow_up_date': forms.DateInput(attrs={
                'class': 'form-control',
                'type': 'date'
            }),
        }

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.fields['notes'].required = True
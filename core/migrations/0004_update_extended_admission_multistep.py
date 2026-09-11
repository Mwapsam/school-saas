# Generated manually for multi-step admission form
import django.core.validators
from django.db import migrations, models
import django.db.models.deletion
import core.models


class Migration(migrations.Migration):

    dependencies = [
        ('core', '0003_academicyear_extendedadmissionapplication_and_more'),
    ]

    operations = [
        # Add new fields for multi-step form
        migrations.AddField(
            model_name='extendedadmissionapplication',
            name='current_step',
            field=models.IntegerField(default=1),
        ),
        migrations.AddField(
            model_name='extendedadmissionapplication',
            name='religion',
            field=models.CharField(blank=True, max_length=100),
        ),
        migrations.AddField(
            model_name='extendedadmissionapplication',
            name='birth_place',
            field=models.CharField(blank=True, max_length=255),
        ),
        migrations.AddField(
            model_name='extendedadmissionapplication',
            name='mother_tongue',
            field=models.CharField(blank=True, max_length=100),
        ),
        migrations.AddField(
            model_name='extendedadmissionapplication',
            name='address_line1',
            field=models.CharField(blank=True, max_length=255),
        ),
        migrations.AddField(
            model_name='extendedadmissionapplication',
            name='address_line2',
            field=models.CharField(blank=True, max_length=255),
        ),
        migrations.AddField(
            model_name='extendedadmissionapplication',
            name='city',
            field=models.CharField(blank=True, max_length=100),
        ),
        migrations.AddField(
            model_name='extendedadmissionapplication',
            name='country',
            field=models.ForeignKey(blank=True, null=True, on_delete=django.db.models.deletion.SET_NULL, to='core.country'),
        ),
        migrations.AddField(
            model_name='extendedadmissionapplication',
            name='phone',
            field=models.CharField(blank=True, max_length=20),
        ),
        migrations.AddField(
            model_name='extendedadmissionapplication',
            name='mobile',
            field=models.CharField(blank=True, max_length=20),
        ),
        migrations.AddField(
            model_name='extendedadmissionapplication',
            name='student_photo',
            field=models.FileField(blank=True, null=True, upload_to=core.models.upload_to_photos, validators=[django.core.validators.FileExtensionValidator(allowed_extensions=['jpg', 'jpeg', 'png'])]),
        ),
        migrations.AddField(
            model_name='extendedadmissionapplication',
            name='student_category',
            field=models.ForeignKey(blank=True, null=True, on_delete=django.db.models.deletion.SET_NULL, to='core.studentcategory'),
        ),
        # Guardian 1 fields
        migrations.AddField(
            model_name='extendedadmissionapplication',
            name='guardian1_first_name',
            field=models.CharField(blank=True, max_length=100),
        ),
        migrations.AddField(
            model_name='extendedadmissionapplication',
            name='guardian1_last_name',
            field=models.CharField(blank=True, max_length=100),
        ),
        migrations.AddField(
            model_name='extendedadmissionapplication',
            name='guardian1_relation',
            field=models.CharField(blank=True, max_length=50),
        ),
        migrations.AddField(
            model_name='extendedadmissionapplication',
            name='guardian1_occupation',
            field=models.CharField(blank=True, max_length=200),
        ),
        migrations.AddField(
            model_name='extendedadmissionapplication',
            name='guardian1_office_address_line1',
            field=models.CharField(blank=True, max_length=255),
        ),
        migrations.AddField(
            model_name='extendedadmissionapplication',
            name='guardian1_office_city',
            field=models.CharField(blank=True, max_length=100),
        ),
        migrations.AddField(
            model_name='extendedadmissionapplication',
            name='guardian1_office_phone1',
            field=models.CharField(blank=True, max_length=20),
        ),
        migrations.AddField(
            model_name='extendedadmissionapplication',
            name='guardian1_mobile',
            field=models.CharField(blank=True, max_length=20),
        ),
        migrations.AddField(
            model_name='extendedadmissionapplication',
            name='guardian1_email',
            field=models.EmailField(blank=True, max_length=254),
        ),
        # Guardian 2 fields
        migrations.AddField(
            model_name='extendedadmissionapplication',
            name='guardian2_first_name',
            field=models.CharField(blank=True, max_length=100),
        ),
        migrations.AddField(
            model_name='extendedadmissionapplication',
            name='guardian2_last_name',
            field=models.CharField(blank=True, max_length=100),
        ),
        migrations.AddField(
            model_name='extendedadmissionapplication',
            name='guardian2_relation',
            field=models.CharField(blank=True, max_length=50),
        ),
        migrations.AddField(
            model_name='extendedadmissionapplication',
            name='guardian2_occupation',
            field=models.CharField(blank=True, max_length=200),
        ),
        migrations.AddField(
            model_name='extendedadmissionapplication',
            name='guardian2_office_address_line1',
            field=models.CharField(blank=True, max_length=255),
        ),
        migrations.AddField(
            model_name='extendedadmissionapplication',
            name='guardian2_office_city',
            field=models.CharField(blank=True, max_length=100),
        ),
        migrations.AddField(
            model_name='extendedadmissionapplication',
            name='guardian2_office_phone1',
            field=models.CharField(blank=True, max_length=20),
        ),
        migrations.AddField(
            model_name='extendedadmissionapplication',
            name='guardian2_mobile',
            field=models.CharField(blank=True, max_length=20),
        ),
        migrations.AddField(
            model_name='extendedadmissionapplication',
            name='guardian2_email',
            field=models.EmailField(blank=True, max_length=254),
        ),
        # Previous school fields
        migrations.AddField(
            model_name='extendedadmissionapplication',
            name='previous_school_phone',
            field=models.CharField(blank=True, max_length=20),
        ),
        migrations.AddField(
            model_name='extendedadmissionapplication',
            name='previous_school_email',
            field=models.EmailField(blank=True, max_length=254),
        ),
        migrations.AddField(
            model_name='extendedadmissionapplication',
            name='expected_start_date',
            field=models.DateField(blank=True, null=True),
        ),
        # Health information fields
        migrations.AddField(
            model_name='extendedadmissionapplication',
            name='has_medical_problems',
            field=models.BooleanField(blank=True, null=True),
        ),
        migrations.AddField(
            model_name='extendedadmissionapplication',
            name='recent_hospitalization',
            field=models.BooleanField(blank=True, null=True),
        ),
        migrations.AddField(
            model_name='extendedadmissionapplication',
            name='has_allergies',
            field=models.BooleanField(blank=True, null=True),
        ),
        migrations.AddField(
            model_name='extendedadmissionapplication',
            name='medical_details',
            field=models.TextField(blank=True, help_text='Details if any medical questions answered YES'),
        ),
        # Background information fields
        migrations.AddField(
            model_name='extendedadmissionapplication',
            name='religious_observances',
            field=models.TextField(blank=True, help_text='Special requests for religious observances'),
        ),
        migrations.AddField(
            model_name='extendedadmissionapplication',
            name='background_information',
            field=models.TextField(blank=True, help_text='Background information to help understand the child better'),
        ),
        # Declaration fields
        migrations.AddField(
            model_name='extendedadmissionapplication',
            name='declaration_agreement',
            field=models.BooleanField(default=False),
        ),
        migrations.AddField(
            model_name='extendedadmissionapplication',
            name='declaration_date',
            field=models.DateField(blank=True, null=True),
        ),
        # Modify existing fields
        migrations.AlterField(
            model_name='extendedadmissionapplication',
            name='first_name',
            field=models.CharField(blank=True, max_length=100),
        ),
        migrations.AlterField(
            model_name='extendedadmissionapplication',
            name='last_name',
            field=models.CharField(blank=True, max_length=100),
        ),
        migrations.AlterField(
            model_name='extendedadmissionapplication',
            name='date_of_birth',
            field=models.DateField(blank=True, null=True),
        ),
        migrations.AlterField(
            model_name='extendedadmissionapplication',
            name='gender',
            field=models.CharField(blank=True, choices=[('male', 'Male'), ('female', 'Female'), ('other', 'Other')], max_length=10),
        ),
        migrations.AlterField(
            model_name='extendedadmissionapplication',
            name='status',
            field=models.CharField(choices=[('draft', 'Draft'), ('step1_completed', 'Step 1 Completed'), ('step2_completed', 'Step 2 Completed'), ('step3_completed', 'Step 3 Completed'), ('step4_completed', 'Step 4 Completed'), ('step5_completed', 'Step 5 Completed'), ('submitted', 'Submitted'), ('under_review', 'Under Review'), ('approved', 'Approved'), ('rejected', 'Rejected'), ('waitlisted', 'Waitlisted')], default='draft', max_length=50),
        ),
    ]
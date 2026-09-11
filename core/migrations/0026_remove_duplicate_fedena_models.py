# Generated migration to remove duplicate Fedena models

from django.db import migrations


class Migration(migrations.Migration):

    dependencies = [
        ('core', '0025_add_fedena_migration_models'),
    ]

    operations = [
        # Remove AdminUser model (duplicate of User)
        migrations.DeleteModel(
            name='AdminUser',
        ),

        # Remove Applicant, ApplicantGuardian, ApplicationStatus models (duplicates of AdmissionApplication system)
        migrations.DeleteModel(
            name='ApplicantGuardian',
        ),
        migrations.DeleteModel(
            name='Applicant',
        ),
        migrations.DeleteModel(
            name='ApplicationStatus',
        ),

        # Remove Grade and GradeSet models (duplicates of GradingLevel/GradingType)
        migrations.DeleteModel(
            name='Grade',
        ),
        migrations.DeleteModel(
            name='GradeSet',
        ),

        # Remove SkillAssessment and SubjectSkill models (duplicates of existing skills system)
        migrations.DeleteModel(
            name='SkillAssessment',
        ),
        migrations.DeleteModel(
            name='SubjectSkill',
        ),
    ]
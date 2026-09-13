# Generated migration for school branding and admission configuration

from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('core', '0162_alter_rolepermission_codename'),
    ]

    operations = [
        migrations.AddField(
            model_name='school',
            name='description',
            field=models.TextField(blank=True, null=True, help_text="School's tagline or mission statement"),
        ),
        migrations.AddField(
            model_name='school',
            name='primary_color',
            field=models.CharField(
                blank=True,
                null=True,
                max_length=7,
                help_text="Primary brand color (hex, e.g., #1a7a3c)"
            ),
        ),
        migrations.AddField(
            model_name='school',
            name='secondary_color',
            field=models.CharField(
                blank=True,
                null=True,
                max_length=7,
                help_text="Secondary brand color (hex)"
            ),
        ),
        migrations.AddField(
            model_name='school',
            name='admission_enabled',
            field=models.BooleanField(default=False, help_text="Whether the admission portal is enabled"),
        ),
        migrations.AddField(
            model_name='school',
            name='admission_heading',
            field=models.CharField(
                blank=True,
                null=True,
                max_length=255,
                help_text="Custom heading for the admission portal"
            ),
        ),
        migrations.AddField(
            model_name='school',
            name='admission_cta_text',
            field=models.CharField(
                blank=True,
                null=True,
                max_length=100,
                help_text="Call-to-action button text on admission portal"
            ),
        ),
        migrations.AddField(
            model_name='school',
            name='admission_description',
            field=models.TextField(
                blank=True,
                null=True,
                help_text="Custom description of the admission process"
            ),
        ),
        migrations.AddField(
            model_name='school',
            name='admission_email',
            field=models.EmailField(
                blank=True,
                null=True,
                help_text="Email address for admission inquiries (if different from main email)"
            ),
        ),
        migrations.AddField(
            model_name='school',
            name='social_links',
            field=models.JSONField(
                default=dict,
                blank=True,
                help_text="Social media links (twitter, facebook, instagram, linkedin)"
            ),
        ),
        migrations.AddField(
            model_name='school',
            name='features',
            field=models.JSONField(
                default=dict,
                blank=True,
                help_text="Feature flags (parent_portal, teacher_portal, librarian_portal, hr_portal, etc.)"
            ),
        ),
    ]

# Generated migration for adding employee field to SkillsSubmission

from django.db import migrations, models
import django.db.models.deletion


class Migration(migrations.Migration):

    dependencies = [
        ('core', '0111_teachercomment_class_teacher'),
        ('portal', '0002_skillssubmission'),
    ]

    operations = [
        migrations.AddField(
            model_name='skillssubmission',
            name='employee',
            field=models.ForeignKey(blank=True, null=True, on_delete=django.db.models.deletion.CASCADE, related_name='skills_submissions', to='core.employee', help_text='Null = whole-batch submission (legacy/staff). Set = this teacher\'s own subset only.'),
        ),
        migrations.AlterUniqueTogether(
            name='skillssubmission',
            unique_together={('batch', 'term', 'employee')},
        ),
    ]

# Generated migration for class_teacher field on TeacherComment and SkillsTeacherComment

from django.db import migrations, models
import django.db.models.deletion


class Migration(migrations.Migration):

    dependencies = [
        ('core', '0110_employee_signature_image'),
    ]

    operations = [
        migrations.AddField(
            model_name='teachercomment',
            name='class_teacher',
            field=models.ForeignKey(blank=True, null=True, on_delete=django.db.models.deletion.SET_NULL, related_name='+', to='core.employee', help_text='Teacher resolved as responsible for this student when the row was last saved — stamped by TeacherCommentService, never edited directly. Preserves historical accuracy across reassignment without a temporal date-range query.'),
        ),
        migrations.AddField(
            model_name='skillsteachercomment',
            name='class_teacher',
            field=models.ForeignKey(blank=True, null=True, on_delete=django.db.models.deletion.SET_NULL, related_name='+', to='core.employee', help_text='Teacher resolved as responsible for this student when the row was last saved — stamped by TeacherCommentService, never edited directly. Preserves historical accuracy across reassignment without a temporal date-range query.'),
        ),
    ]

import django.db.models.deletion
import uuid
from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('core', '0072_reporttemplate_skill_category_order'),
    ]

    operations = [
        migrations.CreateModel(
            name='TeacherComment',
            fields=[
                ('id', models.UUIDField(default=uuid.uuid4, editable=False, primary_key=True, serialize=False)),
                ('created_at', models.DateTimeField(auto_now_add=True)),
                ('updated_at', models.DateTimeField(auto_now=True)),
                ('comment', models.TextField(blank=True, default='')),
                ('tenant', models.ForeignKey(
                    on_delete=django.db.models.deletion.CASCADE,
                    related_name='%(class)s_set',
                    to='core.school',
                )),
                ('student', models.ForeignKey(
                    on_delete=django.db.models.deletion.CASCADE,
                    related_name='teacher_comments',
                    to='core.student',
                )),
                ('exam_group', models.ForeignKey(
                    on_delete=django.db.models.deletion.CASCADE,
                    related_name='teacher_comments',
                    to='core.examgroup',
                )),
            ],
            options={
                'unique_together': {('tenant', 'student', 'exam_group')},
            },
        ),
        migrations.AddIndex(
            model_name='teachercomment',
            index=models.Index(fields=['tenant', 'exam_group'], name='core_teache_tenant__examgr_idx'),
        ),
    ]

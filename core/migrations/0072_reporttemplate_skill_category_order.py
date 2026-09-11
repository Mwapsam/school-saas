from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('core', '0071_reporttemplate_subject_order'),
    ]

    operations = [
        migrations.AddField(
            model_name='reporttemplate',
            name='skill_category_order',
            field=models.JSONField(
                default=list,
                help_text='Ordered SkillCategory IDs for the skills checklist in the PDF',
            ),
        ),
    ]

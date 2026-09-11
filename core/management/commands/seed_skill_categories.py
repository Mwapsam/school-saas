"""
Management command to seed default SkillCategory and SkillItem records for a tenant.

These are used by the SKILLS-layout report card (Beginners / Reception / Middle Class).

Usage:
    python manage.py seed_skill_categories --tenant=<tenant_id>
    python manage.py seed_skill_categories --all
    python manage.py seed_skill_categories --all --replace   # wipe & recreate items
"""

from django.core.management.base import BaseCommand
from core.models import School, SkillCategory, SkillItem


DEFAULT_CATEGORIES = [
    {
        'code': 'COMMUNICATION_SKILLS',
        'name': 'Language & Communication',
        'description': 'Listening, speaking, early reading and writing skills',
        'display_order': 1,
        'items': [
            'Listens and follows simple instructions',
            'Communicates needs and feelings verbally',
            'Identifies letters of the alphabet',
            'Identifies letter sounds (phonics)',
            'Holds a pencil/crayon correctly',
            'Writes own name',
            'Recognises own name in print',
            'Retells a simple story',
        ],
    },
    {
        'code': 'CONCEPTUAL_SKILLS',
        'name': 'Mathematics & Numeracy',
        'description': 'Number, shape, measurement and problem-solving skills',
        'display_order': 2,
        'items': [
            'Counts objects 1–10',
            'Identifies numerals 1–10',
            'Matches and sorts by colour',
            'Matches and sorts by shape',
            'Matches and sorts by size',
            'Understands concepts of more / less',
            'Identifies basic shapes (circle, square, triangle, rectangle)',
            'Understands positional language (on, under, beside)',
        ],
    },
    {
        'code': 'MOTOR_SKILLS',
        'name': 'Physical Development',
        'description': 'Gross and fine motor coordination and self-care',
        'display_order': 3,
        'items': [
            'Runs, jumps and hops with coordination',
            'Catches and throws a ball',
            'Uses scissors with control',
            'Completes simple puzzles',
            'Draws recognisable shapes and figures',
            'Manages personal belongings (bag, water bottle)',
        ],
    },
    {
        'code': 'SOCIAL_SKILLS',
        'name': 'Personal & Social Development',
        'description': 'Self-care, cooperation, and relationship-building skills',
        'display_order': 4,
        'items': [
            'Separates from parent / caregiver without distress',
            'Plays cooperatively with peers',
            'Takes turns and shares',
            'Follows classroom rules and routines',
            'Demonstrates self-care (toileting, hand-washing)',
            'Shows respect for others and their belongings',
        ],
    },
    {
        'code': 'CREATIVE_SKILLS',
        'name': 'Creative Arts',
        'description': 'Imagination, music, art and expressive skills',
        'display_order': 5,
        'items': [
            'Participates enthusiastically in songs and rhymes',
            'Engages in imaginative / pretend play',
            'Expresses ideas through drawing or painting',
            'Explores art materials with curiosity',
        ],
    },
    {
        'code': 'CONCENTRATION_SKILLS',
        'name': 'Concentration & Learning Approach',
        'description': 'Attention span, persistence and curiosity',
        'display_order': 6,
        'items': [
            'Sustains attention on a task',
            'Completes a started activity',
            'Shows curiosity and asks questions',
            'Tries again after making a mistake',
        ],
    },
]


class Command(BaseCommand):
    help = 'Seed default skill categories and items for the SKILLS report layout'

    def add_arguments(self, parser):
        parser.add_argument('--tenant', type=str, help='Tenant ID to seed')
        parser.add_argument('--all', action='store_true', help='Seed all tenants')
        parser.add_argument(
            '--replace',
            action='store_true',
            help='Delete existing skill items before re-creating (categories are always kept)',
        )

    def handle(self, *args, **options):
        if options['all']:
            tenants = list(School.objects.all())
            self.stdout.write(f"Seeding skill categories for {len(tenants)} tenant(s)...")
        elif options.get('tenant'):
            try:
                tenants = [School.objects.get(id=options['tenant'])]
            except School.DoesNotExist:
                self.stdout.write(self.style.ERROR(f"Tenant {options['tenant']} not found"))
                return
        else:
            self.stdout.write(self.style.ERROR('Specify --tenant=<id> or --all'))
            return

        replace = options.get('replace', False)
        for tenant in tenants:
            self.stdout.write(f"\n  Tenant: {tenant.name}")
            self._seed(tenant, replace)

        self.stdout.write(self.style.SUCCESS('\n✓ Skill categories seeded successfully!'))

    def _seed(self, tenant, replace: bool):
        for cat_def in DEFAULT_CATEGORIES:
            category, created = SkillCategory.objects.get_or_create(
                tenant=tenant,
                code=cat_def['code'],
                defaults={
                    'name': cat_def['name'],
                    'description': cat_def['description'],
                    'display_order': cat_def['display_order'],
                    'is_active': True,
                },
            )
            if created:
                self.stdout.write(f"    + Created category: {category.name}")
            else:
                self.stdout.write(f"    ~ Exists: {category.name}")

            if replace:
                SkillItem.objects.filter(category=category, tenant=tenant).delete()

            for order, description in enumerate(cat_def['items'], start=1):
                item, item_created = SkillItem.objects.get_or_create(
                    tenant=tenant,
                    category=category,
                    description=description,
                    defaults={'display_order': order, 'is_active': True},
                )
                if item_created:
                    self.stdout.write(f"        + {description}")

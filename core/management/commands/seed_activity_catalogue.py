"""
Seed the club / sport / other activity catalogue used by the teacher portal's
Term Activities entry (prefilled checkbox options).

Idempotent: re-running only adds anything missing. Creates the three
ActivityProfiles (CLUBS / SPORTS / OTHER) and a sensible default set of
Activities per school. Run for one school with --school-code, otherwise all.
"""
from django.core.management.base import BaseCommand

from core.models import Activity, ActivityProfile, School


CATALOGUE = {
    "CLUBS": (
        "Clubs",
        [
            "Art and Craft", "Chess", "Choir", "Computers", "Debate", "Drama",
            "Literacy", "Mathematics", "Poetry and Literature", "Young Farmers",
        ],
    ),
    "SPORTS": (
        "Sports",
        [
            "Aerobics", "Athletics", "Basketball", "Cricket", "Hockey", "Netball",
            "Rugby", "Soccer", "Swimming", "Table Tennis", "Tennis", "Volleyball",
        ],
    ),
    "OTHER": (
        "Other",
        [
            "Assembly", "Handwriting Competition", "ISAZ Athletics", "ISAZ Chess",
            "Spelling Competition",
        ],
    ),
}


class Command(BaseCommand):
    help = "Seed the club/sport/other activity catalogue for the teacher portal."

    def add_arguments(self, parser):
        parser.add_argument(
            "--school-code",
            type=str,
            help="Seed only the school with this code (default: all schools).",
        )

    def handle(self, *args, **options):
        code = options.get("school_code")
        if code:
            schools = list(School.objects.filter(code=code))
            if not schools:
                self.stdout.write(self.style.ERROR(f"No school with code '{code}'."))
                return
        else:
            schools = list(School.objects.all())
            if not schools:
                self.stdout.write(self.style.WARNING("No schools found."))
                return

        for school in schools:
            created_p = created_a = 0
            for name, (display_name, items) in CATALOGUE.items():
                profile, made = ActivityProfile.objects.get_or_create(
                    tenant=school,
                    name=name,
                    defaults={"display_name": display_name, "is_active": True},
                )
                created_p += int(made)
                for item in items:
                    _, made_a = Activity.objects.get_or_create(
                        tenant=school,
                        activity_profile=profile,
                        name=item,
                        defaults={"is_active": True},
                    )
                    created_a += int(made_a)
            self.stdout.write(
                self.style.SUCCESS(
                    f"{school.name}: +{created_p} profiles, +{created_a} activities."
                )
            )

        self.stdout.write(self.style.SUCCESS("Activity catalogue seeding complete."))

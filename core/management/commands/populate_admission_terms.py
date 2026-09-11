"""
Management command to populate default admission terms and conditions for a tenant.
"""

from django.core.management.base import BaseCommand, CommandError
from django.db import transaction

from core.models import School, AdmissionTerms


class Command(BaseCommand):
    help = 'Populate default admission terms and conditions for a tenant'

    def add_arguments(self, parser):
        parser.add_argument(
            'school_code',
            type=str,
            help='The school code (tenant) to populate terms for',
        )
        parser.add_argument(
            '--overwrite',
            action='store_true',
            help='Overwrite existing terms if they already exist',
        )

    def handle(self, *args, **options):
        school_code = options['school_code']
        overwrite = options['overwrite']

        try:
            # Get the school (tenant)
            school = School.objects.get(code=school_code)
            
            # Check if terms already exist
            existing_terms = AdmissionTerms.objects.filter(tenant=school)
            
            if existing_terms.exists() and not overwrite:
                self.stdout.write(
                    self.style.WARNING(
                        f'Admission terms already exist for {school.name} ({school_code}). '
                        'Use --overwrite to replace existing terms.'
                    )
                )
                return
            
            # Delete existing terms if overwrite is enabled
            if overwrite and existing_terms.exists():
                existing_count = existing_terms.count()
                existing_terms.delete()
                self.stdout.write(
                    self.style.SUCCESS(f'Deleted {existing_count} existing terms.')
                )
            
            # Create default terms
            with transaction.atomic():
                self._create_default_terms(school)
            
            self.stdout.write(
                self.style.SUCCESS(
                    f'Successfully populated admission terms for {school.name} ({school_code})'
                )
            )
            
        except School.DoesNotExist:
            raise CommandError(f'School with code "{school_code}" does not exist')
        except Exception as e:
            raise CommandError(f'Error populating admission terms: {str(e)}')

    def _create_default_terms(self, school):
        """Create the default admission terms and conditions."""
        
        # Main Terms and Conditions
        main_terms_content = """
        <h6>CONDITIONS FOR ADMISSION</h6>
        
        <h6>1. Admission</h6>
        <p>Your child's place will be secured by payment of one term's fees, which must be paid in full before admission to class. Failure to pay fees on time may lead to loss of the place.</p>

        <h6>2. Fees</h6>
        <p>Fees are payable termly before the term starts a penalty being charged for payments made after the given deadline. Refunds for whatever reason e.g. illness, holiday, will not be possible.</p>

        <h6>3. Withdrawal</h6>
        <p>In the event of you wishing to withdraw your child at the end of a term you must give at least 30 days notice in writing to the school. Failure to do so will result in payment of fees for the following term regardless of whether your child attends or not. If you withdraw your child during the term, you will be liable for the fees for the remainder of that term.</p>
        <p>The school reserves the right to discontinue any child who persistently behaves in a manner considered harmful to the general learning environment. This includes the persistent and wilful damage to school property.</p>

        <h6>4. Calendar and Timetable</h6>
        <p>Exact term dates will be announced before the end of the preceding term.</p>
        <p>Classes will normally run from Monday to Friday starting at 7:45 hours and ending at 12:00 hours (Pre School) and Primary classes (Grades 1 to 7) end at 13:00 hours. Children should be delivered at the school before 7:30 hours, and it is expected that all children should be collected by 13:30 hours at the latest unless they are attending afternoon activities.</p>
        <p>Persistent late collection of children will be charged to cover the cost of supervision.</p>

        <h6>5. Illness and Accidents</h6>
        <p>In case of emergencies every effort will be made to contact parents/guardians. You are therefore requested to inform the school promptly of any change of address or telephone numbers at home or at work. In the event that you cannot be contacted, the school will automatically seek further medical advice if deemed necessary.</p>
        <p>If the child contracts or comes into contact with any infectious disease, parents must inform the school immediately. A doctor's confirmation of fitness may be required before readmission.</p>
        <p>Whilst every effort will be made to avoid accidents, and supervision will be provided as far as possible at all times, the school will not accept liability for any accidents that may occur on the school premises including all car parking areas.</p>

        <h6>6. Losses</h6>
        <p>The school cannot take responsibility for loss or damage to any of the child's personal property, or the property belonging to anyone within the school premises including all car parking areas. However, every effort will be made to prevent any losses from occurring.</p>

        <h6>7. Clothing and Equipment</h6>
        <p>Children in the Reception and Primary classes must wear school uniform at all times unless otherwise instructed.</p>
        <p>Children in the Nursery should dress in clothes suitable for the rough and tumble of pre-school activities.</p>
        <p>Requirements for any special clothing e.g., P.E. kit will be announced when required.</p>
        <p>Younger children must carry a spare set of essential clothes in case of emergency.</p>
        <p>All clothes and items carried by the child should be clearly labelled.</p>
        """

        # Create the main terms
        AdmissionTerms.objects.create(
            tenant=school,
            title="Terms and Conditions for Admission",
            terms_content=main_terms_content.strip(),
            admission_fee=500.00,  # Default admission fee
            fee_currency="USD",
            order=1,
            is_active=True
        )

        self.stdout.write(
            self.style.SUCCESS('Created default admission terms and conditions')
        )
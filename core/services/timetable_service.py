from typing import Dict, Any, List, Optional
from datetime import datetime, time, timedelta
from django.db.models import QuerySet
from django.db import transaction

from core.models import Timetable, Weekday, ClassTiming, Batch
from .base import TenantAwareService
from .exceptions import ValidationException, NotFoundException
from .logging_service import ServiceLogger, logged_operation


class TimetableService(TenantAwareService[Timetable]):
    def __init__(self, tenant):
        super().__init__(Timetable, tenant)
        self.logger = ServiceLogger('timetable', tenant)
    
    def get_timetables(
        self, 
        batch_id: str = None, 
        weekday_id: str = None,
        include_related: bool = True
    ) -> QuerySet[Timetable]:
        """Get timetables with optional filtering"""
        queryset = self.get_base_queryset()
        
        if batch_id:
            queryset = queryset.filter(batch_id=batch_id)
        
        if weekday_id:
            queryset = queryset.filter(weekday_id=weekday_id)
        
        if include_related:
            queryset = queryset.select_related(
                'batch', 'weekday', 'class_timing', 'subject', 'employee'
            )
        
        return queryset
    
    def get_batch_timetable(self, batch_id: str) -> List[Dict[str, Any]]:
        """Get structured timetable data for a specific batch"""
        timetables = self.get_timetables(batch_id=batch_id)
        
        # Group by weekday for structured output
        timetable_data = {}
        for timetable in timetables:
            weekday = timetable.weekday.weekday
            if weekday not in timetable_data:
                timetable_data[weekday] = []
            
            timetable_data[weekday].append({
                'id': str(timetable.id),
                'class_timing': {
                    'name': timetable.class_timing.name,
                    'start_time': timetable.class_timing.start_time.strftime('%H:%M'),
                    'end_time': timetable.class_timing.end_time.strftime('%H:%M'),
                    'is_break': timetable.class_timing.is_break
                },
                'subject': {
                    'name': timetable.subject.name if timetable.subject else None,
                    'code': timetable.subject.code if timetable.subject else None,
                } if timetable.subject else None,
                'employee': {
                    'name': f"{timetable.employee.first_name} {timetable.employee.last_name}" if timetable.employee else None,
                } if timetable.employee else None
            })
        
        return timetable_data
    
    def get_weekdays(self) -> QuerySet[Weekday]:
        """Get all weekdays for the tenant"""
        return Weekday.objects.filter(tenant=self.tenant)
    
    def get_timetable_context(self) -> Dict[str, Any]:
        """Get context data for timetable views"""
        return {
            'weekdays': self.get_weekdays(),
            'total_timetables': self.count()
        }

    @logged_operation("build_batch_schedule")
    def build_batch_schedule(
        self,
        batch_id: str,
        period_duration_minutes: int,
        periods_count: int,
        start_time: time,
        breaks: Optional[List[Dict[str, Any]]] = None,
    ) -> List[ClassTiming]:
        """
        Build/rebuild a batch's ClassTiming schedule for a single day.

        This is destructive: it deletes all existing ClassTiming rows for the batch
        and recreates them from scratch. Because Timetable rows cascade on ClassTiming
        deletion, this also clears all subject/employee assignments for the batch.

        Args:
            batch_id: UUID of the batch
            period_duration_minutes: Duration of each regular period in minutes
            periods_count: Number of regular periods per day
            start_time: Start time of the first period (time object)
            breaks: List of break specifications, each with:
                - after_period (int): insert after this period number (0 = before all)
                - duration_minutes (int): break duration
                - label (str): break name (e.g., "Recess", "Lunch")
                - is_lunch (bool): whether this is a lunch break (optional)

        Returns:
            List of newly created ClassTiming objects

        Raises:
            ValidationException: if inputs are invalid
            NotFoundException: if batch doesn't exist
        """
        if period_duration_minutes <= 0:
            raise ValidationException("period_duration_minutes must be > 0")
        if periods_count < 1:
            raise ValidationException("periods_count must be >= 1")
        if breaks is None:
            breaks = []

        # Verify batch exists
        try:
            batch = Batch.objects.get(id=batch_id, tenant=self.tenant)
        except Batch.DoesNotExist:
            raise NotFoundException(f"Batch {batch_id} not found")

        # Validate breaks
        break_positions = set()
        for br in breaks:
            after_period = br.get('after_period', 0)
            if after_period < 0 or after_period > periods_count:
                raise ValidationException(
                    f"Break after_period {after_period} out of range [0, {periods_count}]"
                )
            if after_period in break_positions:
                raise ValidationException(
                    f"Duplicate break at position {after_period}"
                )
            break_positions.add(after_period)

        with transaction.atomic():
            # Delete existing ClassTiming for this batch
            ClassTiming.objects.filter(
                tenant=self.tenant, batch_id=batch_id
            ).delete()

            # Build new ClassTiming rows
            new_timings = []
            current_time = start_time
            period_num = 0

            while period_num < periods_count:
                period_num += 1

                # Create regular period
                end_time = (
                    datetime.combine(datetime.today(), current_time)
                    + timedelta(minutes=period_duration_minutes)
                ).time()

                new_timings.append(
                    ClassTiming(
                        tenant=self.tenant,
                        batch=batch,
                        name=f"Period {period_num}",
                        start_time=current_time,
                        end_time=end_time,
                        is_break=False,
                    )
                )

                current_time = end_time

                # Insert any breaks that come after this period
                for br in breaks:
                    if br.get('after_period') == period_num:
                        break_end = (
                            datetime.combine(datetime.today(), current_time)
                            + timedelta(minutes=br['duration_minutes'])
                        ).time()

                        new_timings.append(
                            ClassTiming(
                                tenant=self.tenant,
                                batch=batch,
                                name=br.get('label', 'Break'),
                                start_time=current_time,
                                end_time=break_end,
                                is_break=True,
                            )
                        )

                        current_time = break_end

            # Bulk create all new ClassTiming rows
            ClassTiming.objects.bulk_create(new_timings)
            self.logger.info(
                f"Built schedule for batch {batch_id}: {len(new_timings)} slots"
            )

            return new_timings
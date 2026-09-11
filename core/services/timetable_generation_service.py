from datetime import time
from typing import List, Dict, Any, Set, Tuple
from dataclasses import dataclass, field
from django.db import transaction
from django.db.models import Q

from core.models import (
    Timetable, Subject, ClassTiming, Weekday, AttendanceSettings,
    Batch, Employee
)
from .exceptions import NotFoundException, ValidationException


@dataclass
class GenerationResult:
    """Result of a timetable generation run."""
    placed_count: int
    unplaced_count: int
    conflicts: List[Dict[str, Any]] = field(default_factory=list)


class TimetableGenerationService:
    """
    Tenant-scoped service for auto-generating a batch's Timetable assignments
    from its Subject requirements and ClassTiming schedule.

    Reads/writes across multiple models (Timetable, Subject, ClassTiming, Weekday,
    AttendanceSettings) and across batches for conflict checks, so it doesn't inherit
    from TenantAwareService but follows a utility-service pattern like SchoolCalendarService.
    """

    def __init__(self, tenant):
        self.tenant = tenant

    def generate(self, batch_id: str) -> GenerationResult:
        """
        Generate/regenerate a complete timetable for a batch.

        Clears existing non-break Timetable entries and creates new ones based on
        Subject requirements, avoiding conflicts with teacher/room bookings.

        Args:
            batch_id: UUID of the batch to generate for

        Returns:
            GenerationResult with placement counts and any conflicts encountered

        Raises:
            NotFoundException: if batch doesn't exist
        """
        # Load batch
        try:
            batch = Batch.objects.get(id=batch_id, tenant=self.tenant)
        except Batch.DoesNotExist:
            raise NotFoundException(f"Batch {batch_id} not found")

        # Load configuration
        try:
            settings = AttendanceSettings.get_settings(self.tenant)
        except Exception:
            settings = AttendanceSettings.objects.create(tenant=self.tenant)

        # Get valid weekdays (those in working_days config)
        valid_weekdays = Weekday.objects.filter(
            tenant=self.tenant,
            day_of_week__in=settings.working_days
        ).order_by('day_of_week')

        # Get instructional slots (non-break ClassTiming rows)
        slots = ClassTiming.objects.filter(
            tenant=self.tenant,
            batch=batch,
            is_break=False,
            is_deleted=False
        ).order_by('start_time')

        # Early exit if config is incomplete
        conflicts = []
        if not valid_weekdays.exists():
            conflicts.append({
                'subject': None,
                'reason': 'No working days configured in attendance settings'
            })
        if not slots.exists():
            conflicts.append({
                'subject': None,
                'reason': 'No instructional periods configured — run the schedule builder first'
            })

        if conflicts:
            return GenerationResult(
                placed_count=0,
                unplaced_count=0,
                conflicts=conflicts
            )

        # Build subject requirements
        subjects = Subject.objects.filter(
            tenant=self.tenant,
            batch=batch
        ).select_related('employee')

        requirements = []
        for subj in subjects:
            if not subj.max_weekly_classes or subj.max_weekly_classes == 0:
                conflicts.append({
                    'subject': subj.name,
                    'reason': 'max_weekly_classes not set — skipped'
                })
                continue

            # Build requirement units (doubles + singles)
            if subj.prefer_consecutive and subj.max_weekly_classes >= 2:
                pairs = subj.max_weekly_classes // 2
                remainder = subj.max_weekly_classes % 2
                requirements.extend([
                    {'subject': subj, 'size': 2}
                    for _ in range(pairs)
                ])
                if remainder:
                    requirements.append({'subject': subj, 'size': 1})
            else:
                requirements.extend([
                    {'subject': subj, 'size': 1}
                    for _ in range(subj.max_weekly_classes)
                ])

        # Sort by constraint: prefer consecutive first, then by volume
        requirements.sort(
            key=lambda r: (
                -(1 if r['size'] == 2 else 0),
                -r['subject'].max_weekly_classes,
                str(r['subject'].id)
            )
        )

        # Initialize constraint tracking
        batch_slot_used: Set[Tuple[str, str]] = set()
        teacher_busy: Dict[str, Set[Tuple[int, str, str]]] = {}
        classroom_busy: Dict[str, Set[Tuple[int, str, str]]] = {}
        subject_day_count: Dict[Tuple[str, int], int] = {}

        # Seed teacher/room busy from OTHER batches (live conflicts to avoid)
        other_timetables = Timetable.objects.filter(
            tenant=self.tenant,
        ).exclude(
            batch=batch
        ).select_related(
            'employee', 'class_timing', 'weekday'
        )

        for entry in other_timetables:
            if entry.employee:
                key = str(entry.employee.id)
                if key not in teacher_busy:
                    teacher_busy[key] = set()

                teacher_busy[key].add((
                    entry.weekday.day_of_week,
                    entry.class_timing.start_time.isoformat(),
                    entry.class_timing.end_time.isoformat()
                ))

            if entry.classroom:
                if entry.classroom not in classroom_busy:
                    classroom_busy[entry.classroom] = set()

                classroom_busy[entry.classroom].add((
                    entry.weekday.day_of_week,
                    entry.class_timing.start_time.isoformat(),
                    entry.class_timing.end_time.isoformat()
                ))

        # Try to place each requirement
        to_create: List[Timetable] = []
        unplaced = []

        for req in requirements:
            subj = req['subject']
            size = req['size']
            placed = False

            # Build candidate list in spread order (favor underused days for this subject)
            day_usage = {wd.id: 0 for wd in valid_weekdays}
            for (subj_id, wd_id), count in subject_day_count.items():
                if str(subj_id) == str(subj.id):
                    day_usage[wd_id] = count

            sorted_days = sorted(
                valid_weekdays,
                key=lambda wd: (day_usage[wd.id], wd.day_of_week)
            )

            # Try to place with soft "don't repeat same subject same day" constraint
            for soft_constraint_relaxed in [False, True]:
                if placed:
                    break

                for weekday in sorted_days:
                    if placed:
                        break

                    for slot_idx, slot in enumerate(slots):
                        if placed:
                            break

                        # For double-period, check pair availability
                        if size == 2:
                            if slot_idx + 1 >= len(slots):
                                continue  # Not enough slots left for a pair

                            next_slot = slots[slot_idx + 1]

                            # Check both slots are free
                            slot_key1 = (str(weekday.id), str(slot.id))
                            slot_key2 = (str(weekday.id), str(next_slot.id))

                            if (slot_key1 in batch_slot_used or
                                    slot_key2 in batch_slot_used):
                                continue

                            # Check no teacher conflict on either slot
                            if subj.employee:
                                emp_key = str(subj.employee.id)
                                if emp_key in teacher_busy:
                                    if (self._time_overlaps(
                                        weekday.day_of_week,
                                        slot.start_time,
                                        next_slot.end_time,
                                        teacher_busy[emp_key]
                                    )):
                                        continue

                            # Check soft constraint: same subject same day
                            if not soft_constraint_relaxed:
                                day_key = (str(subj.id), weekday.id)
                                if subject_day_count.get(day_key, 0) > 0:
                                    continue

                            # All constraints pass — place both periods
                            batch_slot_used.add(slot_key1)
                            batch_slot_used.add(slot_key2)

                            to_create.append(
                                Timetable(
                                    tenant=self.tenant,
                                    batch=batch,
                                    weekday=weekday,
                                    class_timing=slot,
                                    subject=subj,
                                    employee=subj.employee
                                )
                            )
                            to_create.append(
                                Timetable(
                                    tenant=self.tenant,
                                    batch=batch,
                                    weekday=weekday,
                                    class_timing=next_slot,
                                    subject=subj,
                                    employee=subj.employee
                                )
                            )

                            # Update tracking
                            day_key = (str(subj.id), weekday.id)
                            subject_day_count[day_key] = subject_day_count.get(day_key, 0) + 1

                            if subj.employee:
                                emp_key = str(subj.employee.id)
                                if emp_key not in teacher_busy:
                                    teacher_busy[emp_key] = set()
                                teacher_busy[emp_key].add((
                                    weekday.day_of_week,
                                    slot.start_time.isoformat(),
                                    next_slot.end_time.isoformat()
                                ))

                            placed = True

                        else:
                            # Single period
                            slot_key = (str(weekday.id), str(slot.id))

                            if slot_key in batch_slot_used:
                                continue

                            # Check teacher conflict
                            if subj.employee:
                                emp_key = str(subj.employee.id)
                                if emp_key in teacher_busy:
                                    if (self._time_overlaps(
                                        weekday.day_of_week,
                                        slot.start_time,
                                        slot.end_time,
                                        teacher_busy[emp_key]
                                    )):
                                        continue

                            # Check soft constraint: same subject same day
                            if not soft_constraint_relaxed:
                                day_key = (str(subj.id), weekday.id)
                                if subject_day_count.get(day_key, 0) > 0:
                                    continue

                            # All constraints pass
                            batch_slot_used.add(slot_key)

                            to_create.append(
                                Timetable(
                                    tenant=self.tenant,
                                    batch=batch,
                                    weekday=weekday,
                                    class_timing=slot,
                                    subject=subj,
                                    employee=subj.employee
                                )
                            )

                            # Update tracking
                            day_key = (str(subj.id), weekday.id)
                            subject_day_count[day_key] = subject_day_count.get(day_key, 0) + 1

                            if subj.employee:
                                emp_key = str(subj.employee.id)
                                if emp_key not in teacher_busy:
                                    teacher_busy[emp_key] = set()
                                teacher_busy[emp_key].add((
                                    weekday.day_of_week,
                                    slot.start_time.isoformat(),
                                    slot.end_time.isoformat()
                                ))

                            placed = True

            if not placed:
                unplaced.append(req)

        # Generate conflict descriptions for unplaced
        for req in unplaced:
            subj = req['subject']
            reason = (
                f"Cannot place {req['size']}-period block without conflicts "
                "(teacher or slot busy)"
            )
            conflicts.append({
                'subject': subj.name,
                'reason': reason
            })

        # Persist
        with transaction.atomic():
            # Delete existing non-break Timetable rows for this batch
            Timetable.objects.filter(
                tenant=self.tenant,
                batch=batch,
                class_timing__is_break=False
            ).delete()

            # Bulk create new assignments
            if to_create:
                Timetable.objects.bulk_create(to_create)

        return GenerationResult(
            placed_count=len(to_create),
            unplaced_count=len(unplaced),
            conflicts=conflicts
        )

    def _time_overlaps(
        self,
        day_of_week: int,
        start_time: time,
        end_time: time,
        busy_set: Set[Tuple[int, str, str]]
    ) -> bool:
        """Check if a time slot overlaps with any busy period on the same day."""
        for busy_day, busy_start_str, busy_end_str in busy_set:
            if busy_day != day_of_week:
                continue

            busy_start = time.fromisoformat(busy_start_str)
            busy_end = time.fromisoformat(busy_end_str)

            # Overlap: (start_a < end_b) and (start_b < end_a)
            if start_time < busy_end and busy_start < end_time:
                return True

        return False

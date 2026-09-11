"""
PortalAccountService — provisions login accounts for the Parent & Teacher portal.

This is the single black box for turning a person (teacher or parent) into a
portal-capable account. It guarantees the two invariants the portal depends on:

  1. The ``User`` has a usable Django password (``set_password``) and is active,
     so it authenticates through ``ModelBackend`` (which SimpleJWT uses).
  2. The ``User`` is linked to the right profile — ``Employee`` (→ teacher role)
     or ``Guardian`` (→ parent role) — and joined to the tenant.

Role detection itself lives in ``portal.roles``; this service only creates the
relationships that role detection reads.
"""
from __future__ import annotations

import logging
import re
import secrets
from datetime import date
from typing import Iterable

from django.db import transaction

from core.models import (
    Employee,
    Guardian,
    Student,
    StudentGuardianRelation,
    User,
)
from .exceptions import DuplicateException, NotFoundException, ValidationException

logger = logging.getLogger(__name__)


class PortalAccountService:
    def __init__(self, tenant):
        if tenant is None:
            raise ValidationException("A tenant is required to create accounts.")
        self.tenant = tenant

    # ── shared helpers ────────────────────────────────────────────────────────

    def _normalize_username(self, username: str) -> str:
        username = (username or "").strip().lower()
        if len(username) < 3:
            raise ValidationException("Username must be at least 3 characters long.")
        if not username.replace("_", "").replace("-", "").replace(".", "").isalnum():
            raise ValidationException(
                "Username may only contain letters, numbers, '.', '_' and '-'."
            )
        if User.objects.filter(username=username).exists():
            raise DuplicateException(f"Username '{username}' is already taken.")
        return username

    def _create_login_user(
        self,
        *,
        username: str,
        password: str,
        first_name: str,
        last_name: str,
        email: str | None,
    ) -> User:
        if not first_name or not last_name:
            raise ValidationException("First and last name are required.")
        if not password or len(password) < 8:
            raise ValidationException("Password must be at least 8 characters long.")

        username = self._normalize_username(username)

        user = User(
            username=username,
            email=(email or "").strip().lower() or None,
            first_name=first_name.strip(),
            last_name=last_name.strip(),
            is_active=True,
            is_admin=False,
            password_change_required=True,
        )
        user.set_password(password)  # standard Django password → portal login works
        user.save()
        user.tenants.add(self.tenant)
        return user

    # ── teachers ──────────────────────────────────────────────────────────────

    @transaction.atomic
    def create_teacher_account(
        self,
        *,
        first_name: str,
        last_name: str,
        username: str,
        password: str,
        employee_number: str,
        gender_male: bool,
        joining_date: date | None = None,
        email: str | None = None,
        job_title: str | None = None,
        mobile_phone: str | None = None,
    ) -> tuple[User, Employee]:
        if not employee_number or not employee_number.strip():
            raise ValidationException("Employee number is required.")
        employee_number = employee_number.strip()
        if Employee.objects.filter(employee_number=employee_number).exists():
            raise DuplicateException(
                f"Employee number '{employee_number}' already exists."
            )

        user = self._create_login_user(
            username=username,
            password=password,
            first_name=first_name,
            last_name=last_name,
            email=email,
        )

        employee = Employee.objects.create(
            tenant=self.tenant,
            employee_number=employee_number,
            first_name=first_name.strip(),
            last_name=last_name.strip(),
            joining_date=joining_date or date.today(),
            gender=bool(gender_male),
            job_title=(job_title or "").strip() or None,
            email=user.email,
            mobile_phone=(mobile_phone or "").strip() or None,
            user=user,
            status=True,
        )

        logger.info(
            "portal.account teacher created tenant=%s user=%s employee=%s",
            getattr(self.tenant, "schema_name", "?"),
            user.username,
            employee.employee_number,
        )
        return user, employee

    # ── grant access to an existing teacher/parent ─────────────────────────────

    @transaction.atomic
    def grant_portal_access(
        self,
        *,
        profile_type: str,
        profile_id: str,
        username: str,
        password: str,
        email: str | None = None,
    ) -> User:
        """Create and link a portal login for an existing Employee or Guardian
        that doesn't have one yet."""
        if profile_type == "employee":
            profile = Employee.objects.filter(id=profile_id).first()
        elif profile_type == "guardian":
            profile = Guardian.objects.filter(id=profile_id).first()
        else:
            raise ValidationException("Unknown profile type.")

        if profile is None:
            raise NotFoundException("This person could not be found.")

        existing = getattr(profile, "user", None)
        if existing is not None and not existing.is_admin:
            raise ValidationException("This person already has a portal login.")

        user = self._create_login_user(
            username=username,
            password=password,
            first_name=profile.first_name,
            last_name=profile.last_name,
            email=email or getattr(profile, "email", None),
        )
        profile.user = user
        profile.save(update_fields=["user"])

        logger.info(
            "portal.account access granted tenant=%s user=%s profile=%s:%s",
            getattr(self.tenant, "schema_name", "?"),
            user.username,
            profile_type,
            profile_id,
        )
        return user

    @transaction.atomic
    def link_existing_login(self, *, profile_type: str, profile_id: str, user: User) -> User:
        """Attach an existing portal ``User`` to a second profile so one account
        covers multiple roles (e.g. a teacher who is also a parent).

        The target profile must not already be linked to a login. The user must
        be a real portal login (not an ``is_admin`` dashboard account).
        """
        if profile_type == "employee":
            profile = Employee.objects.filter(id=profile_id).first()
        elif profile_type == "guardian":
            profile = Guardian.objects.filter(id=profile_id).first()
        else:
            raise ValidationException("Unknown profile type.")

        if profile is None:
            raise NotFoundException("This person could not be found.")
        if user is None or getattr(user, "is_admin", False):
            raise ValidationException("A portal login is required to link a role.")

        existing = getattr(profile, "user", None)
        if existing is not None and existing.id != user.id:
            raise ValidationException("This record is already linked to a different login.")

        profile.user = user
        profile.save(update_fields=["user"])

        logger.info(
            "portal.account role linked tenant=%s user=%s profile=%s:%s",
            getattr(self.tenant, "schema_name", "?"),
            user.username,
            profile_type,
            profile_id,
        )
        return user

    def send_credentials_sms(self, guardian: Guardian, *, username: str, password: str) -> dict:
        """Text a parent their new portal login. Best-effort — never raises;
        callers should treat account creation as successful regardless of the
        SMS outcome."""
        if not guardian.mobile_phone:
            return {
                "success": False,
                "message": "SMS not sent",
                "error": f"Guardian {guardian.id} has no phone number",
            }

        message = (
            f"Hello {guardian.first_name}, your {self.tenant.name} parent portal "
            f"login has been created. Username: {username}  Password: {password}  "
            f"Please log in and change your password."
        )
        try:
            from utils.sms_client import SMSClient

            result = SMSClient.send_sms(
                recipients=guardian.mobile_phone,
                message=message,
                sender_id=self.tenant.name,
                enqueue=False,
            )
            if result:
                return {
                    "success": True,
                    "message": f"SMS sent to {guardian.mobile_phone}",
                    "error": None,
                }
            return {
                "success": False,
                "message": "SMS sending failed",
                "error": "SMS provider returned no response",
            }
        except Exception as e:
            logger.error("Error sending credentials SMS to guardian %s: %s", guardian.id, e)
            return {"success": False, "message": "SMS sending failed", "error": str(e)}

    # ── parents ───────────────────────────────────────────────────────────────

    def _resolve_students(self, student_ids: Iterable[str] | None) -> list[Student]:
        students: list[Student] = []
        for sid in list(student_ids or []):
            if not sid:
                continue
            student = Student.objects.filter(id=sid).first()
            if student is None:
                raise NotFoundException(f"Student {sid} was not found.")
            students.append(student)
        return students

    @staticmethod
    def _same_person(guardian: Guardian, first_name: str | None, last_name: str | None) -> bool:
        """True when the typed name matches the guardian on file. Used to stop a
        shared family email/phone from collapsing two different parents (e.g.
        mother + father) into one account."""
        if not first_name or not last_name:
            # No name to compare against — fall back to the contact match alone.
            return True
        return (
            guardian.first_name.strip().casefold() == first_name.strip().casefold()
            and guardian.last_name.strip().casefold() == last_name.strip().casefold()
        )

    def find_existing_guardian(
        self,
        *,
        email: str | None = None,
        mobile: str | None = None,
        first_name: str | None = None,
        last_name: str | None = None,
    ) -> Guardian | None:
        """Look up a guardian already on file for this tenant by exact email
        (case-insensitive) then exact mobile phone — the same match rule the
        admission flow uses to avoid provisioning a second account for a
        parent who already has one.

        When ``first_name``/``last_name`` are given, a contact match is only
        honoured if the name matches too: families share one phone and one
        email, so a bare contact hit is not proof it is the same person."""
        guardian = None
        if email:
            guardian = Guardian.objects.filter(
                tenant=self.tenant, email__iexact=email
            ).first()
            if guardian is not None and not self._same_person(guardian, first_name, last_name):
                guardian = None
        if guardian is None and mobile:
            guardian = Guardian.objects.filter(
                tenant=self.tenant, mobile_phone=mobile
            ).first()
            if guardian is not None and not self._same_person(guardian, first_name, last_name):
                guardian = None
        return guardian

    @transaction.atomic
    def create_parent_account(
        self,
        *,
        first_name: str,
        last_name: str,
        username: str,
        password: str,
        relation: str,
        email: str | None = None,
        mobile_phone: str | None = None,
        student_ids: Iterable[str] | None = None,
    ) -> tuple[User, Guardian]:
        relation = (relation or "").strip() or "Guardian"

        # Validate any students up front so we fail before creating the user.
        students = self._resolve_students(student_ids)

        user = self._create_login_user(
            username=username,
            password=password,
            first_name=first_name,
            last_name=last_name,
            email=email,
        )

        guardian = Guardian.objects.create(
            tenant=self.tenant,
            first_name=first_name.strip(),
            last_name=last_name.strip(),
            relation=relation,
            email=user.email,
            mobile_phone=(mobile_phone or "").strip() or None,
            user=user,
            is_active=True,
        )

        for index, student in enumerate(students):
            StudentGuardianRelation.objects.get_or_create(
                tenant=self.tenant,
                student=student,
                guardian=guardian,
                defaults={
                    "relation": relation,
                    "is_immediate_contact": index == 0,
                    "school": self.tenant,
                },
            )
            # Make this guardian the student's immediate contact if none set.
            if index == 0 and student.immediate_contact_id is None:
                student.immediate_contact = guardian
                student.save(update_fields=["immediate_contact"])

        logger.info(
            "portal.account parent created tenant=%s user=%s guardian=%s children=%d",
            getattr(self.tenant, "schema_name", "?"),
            user.username,
            guardian.id,
            len(students),
        )
        return user, guardian

    @transaction.atomic
    def create_or_reuse_parent_account(
        self,
        *,
        first_name: str,
        last_name: str,
        username: str,
        password: str,
        relation: str,
        email: str | None = None,
        mobile_phone: str | None = None,
        student_ids: Iterable[str] | None = None,
    ) -> dict:
        """Admin-triggered "Add Parent" entry point: reuses an existing
        guardian (matched by email/mobile) instead of creating a duplicate
        when a parent already has a student in the system.

        Returns {"status": "created"|"reused"|"granted_login", "username",
        "guardian_name"}.
        """
        email = (email or "").strip() or None
        mobile_phone = (mobile_phone or "").strip() or None
        relation = (relation or "").strip() or "Guardian"
        students = self._resolve_students(student_ids)

        guardian = self.find_existing_guardian(
            email=email,
            mobile=mobile_phone,
            first_name=first_name,
            last_name=last_name,
        )

        if guardian is None:
            user, guardian = self.create_parent_account(
                first_name=first_name,
                last_name=last_name,
                username=username,
                password=password,
                relation=relation,
                email=email,
                mobile_phone=mobile_phone,
                student_ids=student_ids,
            )
            return {
                "status": "created",
                "username": user.username,
                "guardian_name": f"{guardian.first_name} {guardian.last_name}",
            }

        for student in students:
            self._link_student_to_guardian(student, guardian, relation)

        guardian_name = f"{guardian.first_name} {guardian.last_name}"

        if guardian.user_id is not None:
            logger.info(
                "portal.account parent reused tenant=%s guardian=%s children=%d",
                getattr(self.tenant, "schema_name", "?"),
                guardian.id,
                len(students),
            )
            return {
                "status": "reused",
                "username": guardian.user.username,
                "guardian_name": guardian_name,
            }

        # Guardian record exists but never got a login — grant one now using
        # the credentials submitted on this form.
        self.grant_portal_access(
            profile_type="guardian",
            profile_id=str(guardian.id),
            username=username,
            password=password,
            email=email,
        )
        logger.info(
            "portal.account parent granted login tenant=%s guardian=%s children=%d",
            getattr(self.tenant, "schema_name", "?"),
            guardian.id,
            len(students),
        )
        return {
            "status": "granted_login",
            "username": username,
            "guardian_name": guardian_name,
        }

    # ── automatic parent provisioning at admission ────────────────────────────

    def generate_unique_username(self, base: str) -> str:
        """Turn a free-form base (email local-part or name) into an available
        username matching _normalize_username's rules, suffixing digits on
        collision instead of raising."""
        candidate = re.sub(r"[^a-z0-9._-]", "", (base or "").strip().lower())
        candidate = candidate.strip("._-") or "parent"
        if len(candidate) < 3:
            candidate = f"{candidate}{secrets.token_hex(2)}"

        if not User.objects.filter(username=candidate).exists():
            return candidate
        for suffix in range(2, 52):
            attempt = f"{candidate}{suffix}"
            if not User.objects.filter(username=attempt).exists():
                return attempt
        return f"{candidate}{secrets.token_hex(4)}"

    def generate_password(self) -> str:
        return secrets.token_urlsafe(9)

    def _link_student_to_guardian(self, student: Student, guardian: Guardian, relation: str) -> None:
        StudentGuardianRelation.objects.get_or_create(
            tenant=self.tenant,
            student=student,
            guardian=guardian,
            defaults={
                "relation": relation,
                "is_immediate_contact": student.immediate_contact_id is None,
                "school": self.tenant,
            },
        )
        if student.immediate_contact_id is None:
            student.immediate_contact = guardian
            student.save(update_fields=["immediate_contact"])

    def provision_parent_account_from_application(self, application, student: Student) -> dict:
        """
        Create (or reuse) a parent portal account for guardian 1 of an admitted
        admission application, and link the student to that guardian.

        Returns a dict for the admit API response:
          {"status": "created"|"reused"|"skipped",
           "username", "password", "guardian_name", "reason"}
        The password is present only when a brand-new login was created — it is
        shown once to the admin and never recoverable afterwards.
        """
        first_name = (application.guardian1_first_name or "").strip()
        last_name = (application.guardian1_last_name or "").strip()
        if not first_name or not last_name:
            return {
                "status": "skipped",
                "reason": "The application has no guardian name to create an account from.",
            }

        email = (application.guardian1_email or "").strip()
        mobile = (application.guardian1_mobile or "").strip()
        relation = (application.guardian1_relation or "").strip() or "Guardian"
        guardian_name = f"{first_name} {last_name}"

        guardian = self.find_existing_guardian(
            email=email or None,
            mobile=mobile or None,
            first_name=first_name,
            last_name=last_name,
        )

        if guardian is not None:
            self._link_student_to_guardian(student, guardian, relation)

            if guardian.user_id is not None:
                logger.info(
                    "portal.account parent reused tenant=%s guardian=%s student=%s",
                    getattr(self.tenant, "schema_name", "?"),
                    guardian.id,
                    student.admission_no,
                )
                return {
                    "status": "reused",
                    "username": guardian.user.username,
                    "guardian_name": f"{guardian.first_name} {guardian.last_name}",
                    "reason": "An account for this guardian already exists; the student was linked to it.",
                }

            # Guardian record exists but never got a login — grant one now.
            username = self.generate_unique_username(
                email.split("@")[0] if email else f"{first_name}.{last_name}"
            )
            password = self.generate_password()
            self.grant_portal_access(
                profile_type="guardian",
                profile_id=str(guardian.id),
                username=username,
                password=password,
                email=email or None,
            )
            return {
                "status": "created",
                "username": username,
                "password": password,
                "guardian_name": f"{guardian.first_name} {guardian.last_name}",
            }

        username = self.generate_unique_username(
            email.split("@")[0] if email else f"{first_name}.{last_name}"
        )
        password = self.generate_password()
        _, guardian = self.create_parent_account(
            first_name=first_name,
            last_name=last_name,
            username=username,
            password=password,
            relation=relation,
            email=email or None,
            mobile_phone=mobile or None,
            student_ids=[str(student.id)],
        )

        # Carry over the extra details the parent submitted on the application.
        guardian.occupation = (application.guardian1_occupation or "").strip()
        guardian.office_phone = (application.guardian1_office_phone1 or "").strip()
        guardian.office_address_line1 = (application.guardian1_office_address_line1 or "").strip()
        guardian.city = (application.guardian1_office_city or "").strip()
        guardian.save(update_fields=["occupation", "office_phone", "office_address_line1", "city"])

        return {
            "status": "created",
            "username": username,
            "password": password,
            "guardian_name": guardian_name,
        }

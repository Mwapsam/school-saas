from django.shortcuts import render, redirect, get_object_or_404
from django.http import JsonResponse
from django.views import View
from django.views.generic import TemplateView
from django.contrib import messages
from django.db import transaction
from django.db.models import Q, Count, Sum, ProtectedError
from collections import defaultdict
from datetime import date, timedelta

from core.services.exceptions import BusinessLogicException, DuplicateException, NotFoundException, ValidationException
from core.authz.mixins import PermissionRequiredMixin

from ..models import (
    Book, BookCategory, BookMovement, Library, LibraryStaff,
    HostelRoom, HostelFee,
    TransportRoute, Vehicle, TransportFee,
    Assignment, AssignmentAnswer,
    News,
    Student, Employee, Subject, Batch, User,
    Guardian, StudentGuardianRelation,
    Activity, ActivityProfile,
    Sms, Message,
    Role, UserRoleAssignment,
)
from ..services import LibraryService, UserService, CommunicationService
from ..services.role_service import RoleService
from portal.roles import resolve_roles


# ---------------------------------------------------------------------------
# Library
# ---------------------------------------------------------------------------

class LibraryIndexView(TemplateView):
    template_name = 'core/library/index.html'

    def get_context_data(self, **kwargs):
        ctx = super().get_context_data(**kwargs)
        tenant = getattr(self.request, 'tenant', None)
        if not tenant:
            return ctx

        lib = LibraryService(tenant)
        q = self.request.GET.get('q', '').strip()
        category_id = self.request.GET.get('category', '')
        book_type = self.request.GET.get('book_type', '')
        school_level = self.request.GET.get('school_level', '')
        library_id = self.request.GET.get('library', '')
        show = self.request.GET.get('show', 'all')

        if q:
            books = lib.search_books(q, category_id=category_id or None, library_id=library_id or None)
        elif category_id:
            books = lib.get_books_by_category(category_id, library_id=library_id or None)
        elif show == 'available':
            books = lib.get_available_books(library_id=library_id or None)
        else:
            books = lib.get_books(library_id=library_id or None)

        # Apply book type and school level filters
        if book_type:
            books = books.filter(book_type=book_type)
        if school_level:
            books = books.filter(school_level=school_level)

        ctx.update({
            'books': books.select_related('category', 'library'),
            'categories': lib.get_book_categories(),
            'libraries': lib.get_libraries(),
            'library_staff': LibraryStaff.objects.filter(
                tenant=tenant, is_active=True
            ).select_related('employee', 'library').order_by('library__name', 'employee__user__first_name'),
            'stats': lib.get_library_statistics(library_id=library_id or None),
            'issued_books': BookMovement.objects.filter(
                tenant=tenant, is_returned=False
            ).select_related('book', 'student', 'employee').order_by('due_date'),
            'overdue_books': lib.get_overdue_books(library_id=library_id or None).select_related('book', 'student', 'employee'),
            'q': q,
            'selected_category': category_id,
            'selected_book_type': book_type,
            'selected_school_level': school_level,
            'selected_library': library_id,
            'show': show,
            'book_types': dict(Book.BOOK_TYPE_CHOICES),
            'school_levels': dict(Book.SCHOOL_LEVEL_CHOICES),
        })
        return ctx

    def post(self, request, *args, **kwargs):
        tenant = getattr(request, 'tenant', None)
        if not tenant:
            return JsonResponse({'error': 'No tenant'}, status=400)

        action = request.POST.get('action')
        lib = LibraryService(tenant)

        if action == 'add_book':
            try:
                lib.create_book(
                    title=request.POST['title'],
                    author=request.POST['author'],
                    book_number=request.POST['book_number'],
                    category_id=request.POST['category_id'],
                    isbn=request.POST.get('isbn') or None,
                    location=request.POST.get('location') or None,
                    total_copies=int(request.POST.get('total_copies', 1)),
                    book_type=request.POST.get('book_type', 'OTHER'),
                    school_level=request.POST.get('school_level', 'ALL'),
                    barcode=request.POST.get('barcode') or None,
                )
                messages.success(request, 'Book added successfully.')
            except Exception as e:
                messages.error(request, str(e))

        elif action == 'add_category':
            try:
                lib.create_book_category(name=request.POST['name'])
                messages.success(request, 'Category created.')
            except Exception as e:
                messages.error(request, str(e))

        elif action == 'issue_book':
            try:
                due_days = int(request.POST.get('due_days', 14))
                lib.issue_book(
                    book_id=request.POST['book_id'],
                    student_id=request.POST.get('student_id') or None,
                    employee_id=request.POST.get('employee_id') or None,
                    due_date=date.today() + timedelta(days=due_days),
                )
                messages.success(request, 'Book issued successfully.')
            except Exception as e:
                messages.error(request, str(e))

        elif action == 'return_book':
            try:
                lib.return_book(movement_id=request.POST['movement_id'])
                messages.success(request, 'Book returned successfully.')
            except Exception as e:
                messages.error(request, str(e))

        elif action == 'edit_book':
            try:
                book_id = request.POST['book_id']
                lib.update(
                    book_id,
                    title=request.POST['title'],
                    author=request.POST['author'],
                    book_number=request.POST['book_number'],
                    category_id=request.POST['category_id'],
                    isbn=request.POST.get('isbn') or None,
                    barcode=request.POST.get('barcode') or None,
                    location=request.POST.get('location') or None,
                    book_type=request.POST.get('book_type', 'OTHER'),
                    school_level=request.POST.get('school_level', 'ALL'),
                )
                messages.success(request, 'Book updated successfully.')
            except (ValidationException, NotFoundException, DuplicateException, BusinessLogicException) as e:
                messages.error(request, str(e))

        elif action == 'delete_book':
            try:
                book_id = request.POST['book_id']
                if BookMovement.objects.filter(tenant=tenant, book_id=book_id, is_returned=False).exists():
                    raise BusinessLogicException("Cannot delete a book with copies currently issued")
                Book.objects.filter(id=book_id, tenant=tenant).delete()
                messages.success(request, 'Book deleted.')
            except (BusinessLogicException, NotFoundException) as e:
                messages.error(request, str(e))

        elif action == 'add_library':
            try:
                lib.create_library(
                    name=request.POST['name'],
                    code=request.POST.get('code') or None,
                    description=request.POST.get('description') or None,
                )
                messages.success(request, 'Library created successfully.')
            except DuplicateException as e:
                messages.error(request, str(e))
            except Exception as e:
                messages.error(request, f'Error creating library: {str(e)}')

        elif action == 'assign_librarian':
            employee_id = request.POST.get('employee_id')
            library_id = request.POST.get('library_id')
            if not employee_id or not library_id:
                messages.error(request, 'Employee ID and Library ID are required.')
            else:
                try:
                    lib.assign_librarian(employee_id, library_id)
                    messages.success(request, 'Librarian assigned successfully.')
                except NotFoundException as e:
                    messages.error(request, str(e.message))
                except ValidationException as e:
                    messages.error(request, str(e.message))
                except Exception as e:
                    messages.error(request, f'Error assigning librarian: {str(e)}')

        elif action == 'unassign_librarian':
            employee_id = request.POST.get('employee_id')
            library_id = request.POST.get('library_id')
            if not employee_id or not library_id:
                messages.error(request, 'Employee ID and Library ID are required.')
            else:
                try:
                    lib.unassign_librarian(employee_id, library_id)
                    messages.success(request, 'Librarian unassigned successfully.')
                except NotFoundException as e:
                    messages.error(request, str(e.message))
                except Exception as e:
                    messages.error(request, f'Error unassigning librarian: {str(e)}')

        return redirect('core:library')


class LibraryScanView(TemplateView):
    """Handles barcode scan actions via AJAX — separate from the manual form flow
    so each scan gets a fast JSON response instead of a full page reload."""

    def post(self, request, *args, **kwargs):
        tenant = getattr(request, 'tenant', None)
        if not tenant:
            return JsonResponse({'error': 'No tenant'}, status=400)

        action = request.POST.get('action')
        code = request.POST.get('code', '').strip()
        lib = LibraryService(tenant)

        if not code:
            return JsonResponse({'error': 'No barcode provided'}, status=400)

        if action == 'lookup':
            try:
                book = lib.get_book_by_barcode(code)
                return JsonResponse({
                    'id': str(book.id),
                    'title': book.title,
                    'author': book.author,
                    'available_copies': book.available_copies,
                })
            except NotFoundException as e:
                return JsonResponse({'error': str(e)}, status=404)

        elif action == 'issue':
            try:
                due_days = int(request.POST.get('due_days', 14))
                movement = lib.issue_book_by_scan(
                    barcode=code,
                    student_id=request.POST.get('student_id') or None,
                    employee_id=request.POST.get('employee_id') or None,
                    due_date=date.today() + timedelta(days=due_days),
                )
                return JsonResponse({
                    'status': 'issued',
                    'book': movement.book.title,
                    'due_date': str(movement.due_date),
                })
            except (NotFoundException, BusinessLogicException, ValidationException) as e:
                return JsonResponse({'error': str(e)}, status=400)

        elif action == 'return':
            try:
                movement = lib.return_book_by_scan(barcode=code)
                return JsonResponse({
                    'status': 'returned',
                    'book': movement.book.title,
                })
            except (NotFoundException, BusinessLogicException) as e:
                return JsonResponse({'error': str(e)}, status=400)

        return JsonResponse({'error': 'Unknown action'}, status=400)


# ---------------------------------------------------------------------------
# Hostel
# ---------------------------------------------------------------------------

class HostelIndexView(TemplateView):
    template_name = 'core/hostel/index.html'

    def get_context_data(self, **kwargs):
        ctx = super().get_context_data(**kwargs)
        tenant = getattr(self.request, 'tenant', None)
        if not tenant:
            return ctx

        rooms = HostelRoom.objects.filter(tenant=tenant).order_by('room_number')
        assignments = HostelFee.objects.filter(
            tenant=tenant
        ).select_related('student', 'room').order_by('-start_date')

        room_totals = rooms.aggregate(
            total_rooms=Count('id'),
            total_capacity=Sum('capacity'),
        )
        ctx.update({
            'rooms': rooms,
            'assignments': assignments,
            'total_rooms': room_totals['total_rooms'] or 0,
            'total_capacity': room_totals['total_capacity'] or 0,
            'occupied': assignments.filter(end_date__gte=date.today()).count(),
        })
        return ctx

    def post(self, request, *args, **kwargs):
        tenant = getattr(request, 'tenant', None)
        if not tenant:
            return JsonResponse({'error': 'No tenant'}, status=400)

        action = request.POST.get('action')

        if action == 'add_room':
            try:
                HostelRoom.objects.create(
                    room_number=request.POST['room_number'],
                    room_type=request.POST['room_type'],
                    capacity=int(request.POST['capacity']),
                    rent=request.POST['rent'],
                    tenant=tenant,
                )
                messages.success(request, 'Room added.')
            except Exception as e:
                messages.error(request, str(e))

        elif action == 'assign_student':
            try:
                HostelFee.objects.create(
                    student_id=request.POST['student_id'],
                    room_id=request.POST['room_id'],
                    start_date=request.POST['start_date'],
                    end_date=request.POST['end_date'],
                    total_amount=request.POST['total_amount'],
                    tenant=tenant,
                )
                messages.success(request, 'Student assigned to room.')
            except Exception as e:
                messages.error(request, str(e))

        elif action == 'delete_room':
            HostelRoom.objects.filter(id=request.POST['room_id'], tenant=tenant).delete()
            messages.success(request, 'Room removed.')

        return redirect('core:hostel')


# ---------------------------------------------------------------------------
# Transport — see core/view_modules/transport_views.py (rebuilt module).
# ---------------------------------------------------------------------------


# ---------------------------------------------------------------------------
# Assignments
# ---------------------------------------------------------------------------

class AssignmentIndexView(TemplateView):
    template_name = 'core/assignments/index.html'

    def get_context_data(self, **kwargs):
        ctx = super().get_context_data(**kwargs)
        tenant = getattr(self.request, 'tenant', None)
        if not tenant:
            return ctx

        assignments = Assignment.objects.filter(
            tenant=tenant
        ).select_related('subject', 'employee').annotate(
            submission_count=Count('answers')
        ).order_by('-due_date')

        ctx.update({
            'assignments': assignments,
            'subjects': Subject.objects.filter(tenant=tenant, is_deleted=False),
            'employees': Employee.objects.filter(tenant=tenant, status=True),
            'today': date.today(),
        })
        return ctx

    def post(self, request, *args, **kwargs):
        tenant = getattr(request, 'tenant', None)
        if not tenant:
            return JsonResponse({'error': 'No tenant'}, status=400)

        action = request.POST.get('action')

        if action == 'create':
            try:
                Assignment.objects.create(
                    title=request.POST['title'],
                    content=request.POST['content'],
                    subject_id=request.POST['subject_id'],
                    employee_id=request.POST['employee_id'],
                    due_date=request.POST['due_date'],
                    tenant=tenant,
                )
                messages.success(request, 'Assignment created.')
            except Exception as e:
                messages.error(request, str(e))

        elif action == 'delete':
            Assignment.objects.filter(id=request.POST['assignment_id'], tenant=tenant).delete()
            messages.success(request, 'Assignment deleted.')

        return redirect('core:assignments')


class AssignmentDetailView(TemplateView):
    template_name = 'core/assignments/detail.html'

    def get_context_data(self, **kwargs):
        ctx = super().get_context_data(**kwargs)
        tenant = getattr(self.request, 'tenant', None)
        assignment = get_object_or_404(Assignment, id=kwargs['assignment_id'], tenant=tenant)
        submissions = AssignmentAnswer.objects.filter(
            assignment=assignment
        ).select_related('student')

        ctx.update({
            'assignment': assignment,
            'submissions': submissions,
            'submitted_ids': set(submissions.values_list('student_id', flat=True)),
        })
        return ctx

    def post(self, request, *args, **kwargs):
        tenant = getattr(request, 'tenant', None)
        assignment = get_object_or_404(Assignment, id=kwargs['assignment_id'], tenant=tenant)
        action = request.POST.get('action')

        if action == 'grade':
            try:
                answer = get_object_or_404(
                    AssignmentAnswer, id=request.POST['answer_id'], assignment=assignment
                )
                answer.marks = request.POST.get('marks') or None
                answer.remarks = request.POST.get('remarks', '')
                answer.save()
                messages.success(request, 'Grade saved.')
            except Exception as e:
                messages.error(request, str(e))

        return redirect('core:assignment_detail', assignment_id=kwargs['assignment_id'])


# ---------------------------------------------------------------------------
# News
# ---------------------------------------------------------------------------

class NewsIndexView(TemplateView):
    template_name = 'core/news/index.html'

    def get_context_data(self, **kwargs):
        ctx = super().get_context_data(**kwargs)
        tenant = getattr(self.request, 'tenant', None)
        if not tenant:
            return ctx

        ctx['news_list'] = News.objects.filter(tenant=tenant).order_by('-created_at')
        return ctx

    def post(self, request, *args, **kwargs):
        tenant = getattr(request, 'tenant', None)
        if not tenant:
            return JsonResponse({'error': 'No tenant'}, status=400)

        action = request.POST.get('action')

        if action == 'create':
            try:
                news = News(
                    title=request.POST['title'],
                    content=request.POST['content'],
                    author=request.POST.get('author', 'Admin'),
                    is_active='is_active' in request.POST,
                    tenant=tenant,
                )
                # Handle document upload if provided (validation happens at model level)
                if 'document' in request.FILES:
                    news.document = request.FILES['document']

                news.full_clean()  # Run model validators including document size check
                news.save()
                messages.success(request, 'News article published.')
            except Exception as e:
                messages.error(request, str(e))

        elif action == 'edit':
            try:
                news = get_object_or_404(News, id=request.POST['news_id'], tenant=tenant)
                news.title = request.POST['title']
                news.content = request.POST['content']
                news.author = request.POST.get('author', news.author)
                news.is_active = 'is_active' in request.POST

                # Handle document upload if provided (validation happens at model level)
                if 'document' in request.FILES:
                    # Delete old document if it exists
                    if news.document:
                        news.document.delete()
                    news.document = request.FILES['document']

                news.full_clean()  # Run model validators including document size check
                news.save()
                messages.success(request, 'Article updated.')
            except Exception as e:
                messages.error(request, str(e))

        elif action == 'delete':
            News.objects.filter(id=request.POST['news_id'], tenant=tenant).delete()
            messages.success(request, 'Article deleted.')

        elif action == 'toggle':
            news = get_object_or_404(News, id=request.POST['news_id'], tenant=tenant)
            news.is_active = not news.is_active
            news.save()

        return redirect('core:news')


# ---------------------------------------------------------------------------
# User Management
# ---------------------------------------------------------------------------

def _login_user(profile):
    """The dedicated (non-admin) portal login linked to a teacher/parent profile,
    or None. Profiles whose ``user`` points at an admin account (a historical
    mis-link from the old teacher-create flow) are treated as having no login."""
    u = getattr(profile, 'user', None)
    return u if (u and not u.is_admin) else None


class UserManagementView(PermissionRequiredMixin, TemplateView):
    template_name = 'core/users/index.html'
    required_permission = 'settings.users.manage'

    def get_context_data(self, **kwargs):
        ctx = super().get_context_data(**kwargs)
        tenant = getattr(self.request, 'tenant', None)
        if not tenant:
            return ctx

        people = []
        linked_user_ids = set()
        # Profiles with no portal login of their own — candidates for attaching
        # to someone's existing login so one account covers multiple roles.
        unlinked_profiles = []

        # Active RBAC roles held per user login, for the "Roles" column + modal.
        roles_by_user = defaultdict(list)
        for a in (
            UserRoleAssignment.objects.filter(tenant=tenant, is_active=True, role__is_active=True)
            .select_related('role')
        ):
            roles_by_user[str(a.user_id)].append(a.role)

        # Teachers (and other staff) come from the Employee table — the source of
        # truth — regardless of whether they have a portal login yet.
        for e in Employee.objects.select_related('user').order_by('first_name', 'last_name'):
            lu = _login_user(e)
            if lu:
                linked_user_ids.add(lu.id)
            else:
                unlinked_profiles.append({
                    'profile_type': 'employee', 'profile_id': str(e.id),
                    'name': f'{e.first_name} {e.last_name}'.strip(), 'kind': 'Teacher',
                })
            people.append({
                'name': f'{e.first_name} {e.last_name}'.strip(),
                'role': 'teacher',
                'profile_type': 'employee',
                'profile_id': str(e.id),
                'detail': e.employee_number,
                'email': e.email or (lu.email if lu else None),
                'username': lu.username if lu else None,
                'has_login': bool(lu),
                'user_id': str(lu.id) if lu else None,
                'is_active': lu.is_active if lu else e.status,
                'last_login': lu.last_login if lu else None,
                'roles': roles_by_user.get(str(lu.id), []) if lu else [],
                'portal_roles': resolve_roles(lu).ordered() if lu else [],
            })

        # Students attached to each guardian — one query for every guardian,
        # so the table can show (and the bulk-delete flow can be informed by)
        # whether a given parent record is actually in use before it's picked
        # for removal.
        guardian_students = defaultdict(list)
        for rel in (
            StudentGuardianRelation.objects.filter(tenant=tenant)
            .select_related('student')
            .order_by('student__first_name', 'student__last_name')
        ):
            guardian_students[str(rel.guardian_id)].append(rel.student.full_name)

        # Parents come from the Guardian table.
        for g in Guardian.objects.select_related('user').order_by('first_name', 'last_name'):
            lu = _login_user(g)
            if lu:
                linked_user_ids.add(lu.id)
            else:
                unlinked_profiles.append({
                    'profile_type': 'guardian', 'profile_id': str(g.id),
                    'name': f'{g.first_name} {g.last_name}'.strip(), 'kind': 'Parent',
                })
            students_for_guardian = guardian_students.get(str(g.id), [])
            people.append({
                'name': f'{g.first_name} {g.last_name}'.strip(),
                'role': 'parent',
                'profile_type': 'guardian',
                'profile_id': str(g.id),
                'detail': g.relation,
                'email': g.email or (lu.email if lu else None),
                'username': lu.username if lu else None,
                'has_login': bool(lu),
                'user_id': str(lu.id) if lu else None,
                'is_active': lu.is_active if lu else g.is_active,
                'last_login': lu.last_login if lu else None,
                'roles': roles_by_user.get(str(lu.id), []) if lu else [],
                'portal_roles': resolve_roles(lu).ordered() if lu else [],
                'mobile_phone': g.mobile_phone,
                'student_names': students_for_guardian,
                'student_count': len(students_for_guardian),
            })

        # Admin / standalone accounts not tied to a teacher/parent profile.
        standalone = (
            User.objects.filter(tenants=tenant)
            .exclude(id__in=linked_user_ids)
            .order_by('first_name', 'last_name')
        )
        for u in standalone:
            people.append({
                'name': f'{u.first_name} {u.last_name}'.strip() or u.username,
                'role': 'admin' if u.is_admin else 'staff',
                'profile_type': '',
                'profile_id': '',
                'detail': None,
                'email': u.email,
                'username': u.username,
                'has_login': True,
                'user_id': str(u.id),
                'is_active': u.is_active,
                'last_login': u.last_login,
                'roles': roles_by_user.get(str(u.id), []),
                'portal_roles': resolve_roles(u).ordered() if not u.is_admin else [],
            })

        students = Student.objects.filter(
            is_active=True, is_deleted=False
        ).order_by('first_name', 'last_name')

        # Duplicate detection: flag any person sharing a normalized email or
        # username with another person in the list, regardless of role — a
        # teacher and a parent created from the same email typo are just as
        # much a duplicate as two admin accounts. Also flag guardians sharing
        # the same full name (the issue users face when "Link an existing guardian"
        # shows confusing duplicates).
        email_groups = defaultdict(list)
        username_groups = defaultdict(list)
        name_groups = defaultdict(list)  # Parent-only name matching
        for idx, p in enumerate(people):
            if p['email']:
                email_groups[p['email'].strip().lower()].append(idx)
            if p['username']:
                username_groups[p['username'].strip().lower()].append(idx)
            # Only group guardians by name to avoid false positives like
            # a teacher and parent with the same name.
            if p['role'] == 'parent':
                normalized_name = p['name'].strip().lower()
                if normalized_name:
                    name_groups[normalized_name].append(idx)

        duplicate_indexes = set()
        for group in list(email_groups.values()) + list(username_groups.values()) + list(name_groups.values()):
            if len(group) > 1:
                duplicate_indexes.update(group)

        for idx, p in enumerate(people):
            p['is_duplicate'] = idx in duplicate_indexes

        ctx.update({
            'people': people,
            'students': students,
            'all_roles': list(Role.objects.filter(tenant=tenant, is_active=True).order_by('name')),
            'unlinked_profiles': unlinked_profiles,
            'total': len(people),
            'with_login': sum(1 for p in people if p['has_login']),
            'teachers': Employee.objects.count(),
            'parents': Guardian.objects.count(),
            'admins': sum(1 for p in people if p['role'] == 'admin'),
            'duplicates': len(duplicate_indexes),
        })
        return ctx

    def _delete_guardian(self, guardian: Guardian) -> tuple[bool, str]:
        """Delete a guardian record and their portal login (if any).
        Returns (success, message) — True if deleted, False if blocked by foreign key constraint.
        """
        name = f'{guardian.first_name} {guardian.last_name}'.strip()
        login_user = guardian.user
        try:
            with transaction.atomic():
                guardian.delete()
                if login_user is not None:
                    # user.delete() is blocked by django-tenant-users unless
                    # routed through this helper — see its docstring.
                    UserService.hard_delete_user_record(login_user)
            return True, name
        except ProtectedError:
            return False, f'{name} (has invoices on file)'
        except Exception as e:
            return False, f'{name} ({e})'

    def post(self, request, *args, **kwargs):
        tenant = getattr(request, 'tenant', None)
        if not tenant:
            return JsonResponse({'error': 'No tenant'}, status=400)

        action = request.POST.get('action')
        user_service = UserService(tenant)

        if action == 'create':
            try:
                user_service.create_user(
                    username=request.POST['username'],
                    email=request.POST['email'],
                    first_name=request.POST['first_name'],
                    last_name=request.POST['last_name'],
                    password=request.POST['password'],
                    is_admin='is_admin' in request.POST,
                )
                messages.success(request, 'User account created.')
            except Exception as e:
                messages.error(request, str(e))

        elif action == 'create_teacher':
            from ..services.portal_account_service import PortalAccountService
            from datetime import datetime
            try:
                svc = PortalAccountService(tenant)
                joining = request.POST.get('joining_date')
                joining_date = (
                    datetime.strptime(joining, '%Y-%m-%d').date() if joining else None
                )
                _, employee = svc.create_teacher_account(
                    first_name=request.POST['first_name'],
                    last_name=request.POST['last_name'],
                    username=request.POST['username'],
                    password=request.POST['password'],
                    email=request.POST.get('email'),
                    employee_number=request.POST['employee_number'],
                    gender_male=request.POST.get('gender') == 'male',
                    joining_date=joining_date,
                    job_title=request.POST.get('job_title'),
                    mobile_phone=request.POST.get('mobile_phone'),
                )
                messages.success(
                    request,
                    f'Teacher account created for {employee.first_name} '
                    f'{employee.last_name}. They can now sign in to the portal.'
                )
            except Exception as e:
                messages.error(request, str(e))

        elif action == 'create_parent':
            from ..services.portal_account_service import PortalAccountService
            try:
                svc = PortalAccountService(tenant)
                result = svc.create_or_reuse_parent_account(
                    first_name=request.POST['first_name'],
                    last_name=request.POST['last_name'],
                    username=request.POST['username'],
                    password=request.POST['password'],
                    email=request.POST.get('email'),
                    relation=request.POST.get('relation', 'Guardian'),
                    mobile_phone=request.POST.get('mobile_phone'),
                    student_ids=request.POST.getlist('student_ids'),
                )
                if result['status'] == 'reused':
                    messages.info(
                        request,
                        f"{result['guardian_name']} already has a parent account "
                        f"(username \"{result['username']}\") — the selected "
                        f"student(s) were linked to it instead of creating a duplicate."
                    )
                elif result['status'] == 'granted_login':
                    messages.success(
                        request,
                        f"{result['guardian_name']} was already in the system without "
                        f"a login — portal access was enabled and the selected "
                        f"student(s) were linked."
                    )
                else:
                    messages.success(
                        request,
                        f"Parent account created for {result['guardian_name']}. "
                        f"They can now sign in to the portal."
                    )
            except Exception as e:
                messages.error(request, str(e))

        elif action == 'grant_portal_access':
            from ..services.portal_account_service import PortalAccountService
            try:
                svc = PortalAccountService(tenant)
                profile_type = request.POST['profile_type']
                profile_id = request.POST['profile_id']
                username = request.POST['username']
                password = request.POST['password']
                user = svc.grant_portal_access(
                    profile_type=profile_type,
                    profile_id=profile_id,
                    username=username,
                    password=password,
                )
                messages.success(
                    request,
                    f'Portal login enabled — username "{user.username}".'
                )

                if request.POST.get('send_sms') and profile_type == 'guardian':
                    guardian = Guardian.objects.get(id=profile_id)
                    sms_result = svc.send_credentials_sms(
                        guardian, username=username, password=password
                    )
                    if sms_result['success']:
                        messages.success(request, sms_result['message'])
                    else:
                        messages.warning(
                            request,
                            f"Login enabled, but SMS failed: {sms_result['error']}"
                        )
            except Exception as e:
                messages.error(request, str(e))

        elif action == 'link_portal_role':
            from ..services.portal_account_service import PortalAccountService
            try:
                target_user = User.objects.get(id=request.POST['user_id'])
                svc = PortalAccountService(tenant)
                svc.link_existing_login(
                    profile_type=request.POST['profile_type'],
                    profile_id=request.POST['profile_id'],
                    user=target_user,
                )
                messages.success(
                    request,
                    f'{target_user.username} can now use that role in the portal '
                    f'with the same login.'
                )
            except Exception as e:
                messages.error(request, str(e))

        elif action == 'set_roles':
            try:
                target_user_id = request.POST['user_id']
                role_ids = request.POST.getlist('role_ids')
                RoleService(tenant).set_user_roles(
                    target_user_id, role_ids, assigned_by_id=request.user.id, user=request.user,
                )
                messages.success(request, 'Roles updated.')
            except BusinessLogicException as e:
                messages.error(request, str(e.message))
            except Exception as e:
                messages.error(request, str(e))

        elif action == 'deactivate':
            try:
                user_service.deactivate_user(
                    user_id=request.POST['user_id'], performing_user=request.user
                )
                messages.success(request, 'User deactivated.')
            except Exception as e:
                messages.error(request, str(e))

        elif action == 'deactivate_duplicate':
            try:
                profile_type = request.POST.get('profile_type', '')
                profile_id = request.POST.get('profile_id')
                user_id = request.POST.get('user_id')

                if profile_type == 'employee' and profile_id:
                    Employee.objects.filter(id=profile_id, tenant=tenant).update(status=False)
                elif profile_type == 'guardian' and profile_id:
                    Guardian.objects.filter(id=profile_id, tenant=tenant).update(is_active=False)

                if user_id:
                    user_service.deactivate_user(user_id=user_id, performing_user=request.user)

                messages.success(request, 'Duplicate marked inactive.')
            except Exception as e:
                messages.error(request, str(e))

        elif action == 'delete_guardian':
            # Single guardian deletion — admin-only.
            if not getattr(request.user, 'is_admin', False):
                messages.error(request, 'Only administrators can delete guardian records.')
            else:
                try:
                    guardian_id = request.POST.get('guardian_id')
                    guardian = Guardian.objects.filter(id=guardian_id, tenant=tenant).first()
                    if guardian is None:
                        messages.error(request, 'Guardian not found.')
                    else:
                        success, result = self._delete_guardian(guardian)
                        if success:
                            messages.success(
                                request,
                                f"Parent record '{result}' has been permanently removed."
                            )
                        else:
                            messages.error(request, f"Cannot delete: {result}")
                except Exception as e:
                    messages.error(request, str(e))

        elif action == 'bulk_delete_duplicate_guardians':
            guardian_ids = [gid for gid in request.POST.getlist('guardian_ids') if gid]
            if not guardian_ids:
                messages.error(request, 'No duplicate parent records were selected.')
            else:
                deleted, skipped = [], []
                for gid in guardian_ids:
                    guardian = Guardian.objects.filter(id=gid, tenant=tenant).first()
                    if guardian is None:
                        continue
                    success, result = self._delete_guardian(guardian)
                    if success:
                        deleted.append(result)
                    else:
                        skipped.append(result)

                if deleted:
                    messages.success(
                        request,
                        f"Permanently removed {len(deleted)} duplicate parent "
                        f"record(s): {', '.join(deleted)}."
                    )
                if skipped:
                    messages.warning(
                        request,
                        f"Could not remove {len(skipped)}: {'; '.join(skipped)}."
                    )

        elif action == 'activate':
            try:
                target = User.objects.get(id=request.POST['user_id'], tenants=tenant)
                target.is_active = True
                target.save(update_fields=['is_active'])
                messages.success(request, 'User activated.')
            except Exception as e:
                messages.error(request, str(e))

        elif action == 'reset_password':
            try:
                target = User.objects.get(id=request.POST['user_id'], tenants=tenant)
                target.set_password(request.POST['new_password'])
                target.save(update_fields=['password'])
                messages.success(request, 'Password reset successfully.')
            except Exception as e:
                messages.error(request, str(e))

        elif action == 'permanently_delete_user':
            # Admin-gated hard delete: permanently remove the user account
            if not getattr(request.user, 'is_admin', False):
                messages.error(request, 'Only administrators can permanently delete user accounts.')
            else:
                try:
                    target_user_id = request.POST['user_id']
                    target = User.objects.get(id=target_user_id, tenants=tenant)
                    success, message = user_service.permanently_delete_user(
                        user_id=target_user_id, performing_user=request.user
                    )
                    if success:
                        messages.success(request, message)
                    else:
                        messages.error(request, message)
                except User.DoesNotExist:
                    messages.error(request, 'User not found.')
                except Exception as e:
                    messages.error(request, str(e))

        elif action == 'delete_user':
            # Admin-gated soft-delete: only admins can delete users
            if not getattr(request.user, 'is_admin', False):
                messages.error(request, 'Only administrators can delete user accounts.')
            else:
                try:
                    target_user_id = request.POST['user_id']
                    target = User.objects.get(id=target_user_id, tenants=tenant)

                    # Prevent deleting the last admin user
                    can_delete = True
                    if target.is_admin:
                        active_admin_count = User.objects.filter(
                            tenants=tenant, is_admin=True, is_active=True
                        ).exclude(id=target_user_id).count()
                        if active_admin_count == 0:
                            messages.error(
                                request,
                                'Cannot delete the last admin user. Assign admin '
                                'privileges to another user first.'
                            )
                            can_delete = False

                    if can_delete:
                        # Soft-delete: just deactivate the user
                        user_service.deactivate_user(
                            user_id=target_user_id, performing_user=request.user
                        )
                        messages.success(request, f'User "{target.username}" has been deactivated.')
                except User.DoesNotExist:
                    messages.error(request, 'User not found.')
                except Exception as e:
                    messages.error(request, str(e))

        return redirect('core:user_management')


# ---------------------------------------------------------------------------
# Activity catalogue (Clubs / Sports / Other) — feeds the teacher portal's
# Term Activities checkbox pickers.
# ---------------------------------------------------------------------------

# type key -> (canonical profile name, display name)
_ACTIVITY_TYPES = {
    "club": ("CLUBS", "Clubs"),
    "sport": ("SPORTS", "Sports"),
    "other": ("OTHER", "Other"),
}


class ActivityCatalogueView(TemplateView):
    template_name = "core/configuration/activity_catalogue.html"

    def _activities(self, tenant, keyword):
        # Filter at the DB via the profile relation instead of loading every
        # profile into memory and matching in Python.
        return (
            Activity.objects.filter(
                tenant=tenant, activity_profile__name__icontains=keyword
            ).order_by("name")
        )

    def get_context_data(self, **kwargs):
        ctx = super().get_context_data(**kwargs)
        tenant = getattr(self.request, "tenant", None)
        if not tenant:
            return ctx
        ctx["columns"] = [
            {"type": "club", "label": "Clubs", "icon": "fa-people-group",
             "items": list(self._activities(tenant, "CLUB"))},
            {"type": "sport", "label": "Sports", "icon": "fa-futbol",
             "items": list(self._activities(tenant, "SPORT"))},
            {"type": "other", "label": "Other", "icon": "fa-star",
             "items": list(self._activities(tenant, "OTHER"))},
        ]
        return ctx

    def post(self, request, *args, **kwargs):
        tenant = getattr(request, "tenant", None)
        if not tenant:
            return JsonResponse({"error": "No tenant"}, status=400)

        action = request.POST.get("action")

        if action == "add":
            atype = request.POST.get("type")
            name = (request.POST.get("name") or "").strip()
            if atype not in _ACTIVITY_TYPES or not name:
                messages.error(request, "An activity name and type are required.")
            else:
                pname, display = _ACTIVITY_TYPES[atype]
                profile, _ = ActivityProfile.objects.get_or_create(
                    tenant=tenant,
                    name=pname,
                    defaults={"display_name": display, "is_active": True},
                )
                if Activity.objects.filter(
                    tenant=tenant, activity_profile=profile, name__iexact=name
                ).exists():
                    messages.error(request, f'"{name}" already exists.')
                else:
                    Activity.objects.create(
                        tenant=tenant,
                        activity_profile=profile,
                        name=name,
                        is_active=True,
                    )
                    messages.success(request, f'Added "{name}".')

        elif action == "edit":
            activity = Activity.objects.filter(
                id=request.POST.get("id"), tenant=tenant
            ).first()
            name = (request.POST.get("name") or "").strip()
            atype = request.POST.get("type")
            if not activity or not name:
                messages.error(request, "An activity name is required.")
            else:
                # Optionally move the activity to a different type (Clubs/Sports/Other).
                profile = activity.activity_profile
                if atype in _ACTIVITY_TYPES:
                    pname, display = _ACTIVITY_TYPES[atype]
                    profile, _ = ActivityProfile.objects.get_or_create(
                        tenant=tenant, name=pname,
                        defaults={"display_name": display, "is_active": True},
                    )
                if Activity.objects.filter(
                    tenant=tenant, activity_profile=profile, name__iexact=name
                ).exclude(id=activity.id).exists():
                    messages.error(request, f'"{name}" already exists.')
                else:
                    activity.name = name
                    activity.activity_profile = profile
                    activity.save(update_fields=["name", "activity_profile"])
                    messages.success(request, f'Updated "{name}".')

        elif action == "toggle":
            activity = Activity.objects.filter(
                id=request.POST.get("id"), tenant=tenant
            ).first()
            if activity:
                activity.is_active = not activity.is_active
                activity.save(update_fields=["is_active"])
                messages.success(
                    request,
                    f'{activity.name} {"enabled" if activity.is_active else "disabled"}.',
                )

        elif action == "delete":
            activity = Activity.objects.filter(
                id=request.POST.get("id"), tenant=tenant
            ).first()
            if activity:
                name = activity.name
                activity.delete()
                messages.success(request, f'Removed "{name}".')

        elif action == "seed":
            from django.core.management import call_command
            try:
                call_command("seed_activity_catalogue", school_code=tenant.code)
                messages.success(request, "Default catalogue added.")
            except Exception as e:  # pragma: no cover - defensive
                messages.error(request, str(e))

        return redirect("core:activity_catalogue")


# ---------------------------------------------------------------------------
# Communication (SMS + Internal Messages)
# ---------------------------------------------------------------------------

class CommunicationView(TemplateView):
    template_name = 'core/communication/index.html'

    def get_context_data(self, **kwargs):
        ctx = super().get_context_data(**kwargs)
        tenant = getattr(self.request, 'tenant', None)
        if not tenant:
            return ctx

        sms_qs = Sms.objects.filter(tenant=tenant)
        sms_counts = sms_qs.aggregate(
            sent=Count('id', filter=Q(is_sent=True)),
            pending=Count('id', filter=Q(is_sent=False)),
        )
        sms_sent = sms_counts['sent']
        sms_pending = sms_counts['pending']
        sms_history = sms_qs.order_by('-created_at')[:100]

        current_user = getattr(self.request, 'user', None)
        inbox = []
        sent = []
        if current_user and current_user.is_authenticated:
            inbox = Message.objects.filter(recipient=current_user).order_by('-sent_date')[:50]
            sent = Message.objects.filter(sender=current_user).order_by('-sent_date')[:50]

        batches = Batch.objects.filter(tenant=tenant, is_active=True, is_deleted=False).order_by('name')

        ctx.update({
            'sms_history': sms_history,
            'sms_sent': sms_sent,
            'sms_pending': sms_pending,
            'inbox': inbox,
            'sent_messages': sent,
            'users': User.objects.filter(tenants=tenant, is_active=True).exclude(id=getattr(current_user, 'id', None)),
            'batches': batches,
        })
        return ctx

    def post(self, request, *args, **kwargs):
        tenant = getattr(request, 'tenant', None)
        if not tenant:
            return JsonResponse({'error': 'No tenant'}, status=400)

        action = request.POST.get('action')

        if action == 'send_sms':
            recipients = request.POST.getlist('recipients')
            body = request.POST.get('body', '').strip()
            if not body:
                messages.error(request, 'Message body is required.')
            elif not recipients:
                messages.error(request, 'At least one recipient is required.')
            else:
                for phone in recipients:
                    phone = phone.strip()
                    if phone:
                        Sms.objects.create(body=body, recipient=phone, is_sent=False, tenant=tenant)
                messages.success(request, f'SMS queued for {len(recipients)} recipient(s).')

        elif action == 'send_message':
            current_user = getattr(request, 'user', None)
            if not current_user or not current_user.is_authenticated:
                messages.error(request, 'You must be logged in to send messages.')
            else:
                try:
                    recipient = User.objects.get(id=request.POST['recipient_id'], tenants=tenant)
                    Message.objects.create(
                        sender=current_user,
                        recipient=recipient,
                        subject=request.POST.get('subject', '(no subject)'),
                        body=request.POST.get('body', ''),
                        tenant=tenant,
                    )
                    messages.success(request, 'Message sent.')
                except User.DoesNotExist:
                    messages.error(request, 'Recipient not found.')
                except Exception as e:
                    messages.error(request, str(e))

        elif action == 'mark_read':
            current_user = getattr(request, 'user', None)
            if current_user:
                Message.objects.filter(
                    id=request.POST['message_id'], recipient=current_user
                ).update(is_read=True)

        elif action == 'send_batch_sms':
            batch_id = request.POST.get('batch_id')
            body = request.POST.get('body', '').strip()
            send_all = request.POST.get('send_all') == 'true'
            guardian_ids = request.POST.getlist('guardian_ids')

            if not batch_id:
                messages.error(request, 'Please select a batch.')
            elif not body:
                messages.error(request, 'Message body is required.')
            elif not send_all and not guardian_ids:
                messages.error(request, 'Select at least one parent, or choose "Send to all".')
            else:
                service = CommunicationService(tenant)
                result = service.send_batch_sms(
                    batch_id=batch_id,
                    message=body,
                    guardian_ids=guardian_ids if not send_all else None,
                    send_all=send_all,
                    user=getattr(request, 'user', None),
                )
                if result['sent_successfully'] > 0:
                    msg = f"SMS sent to {result['sent_successfully']} parent(s)."
                    if result['failed_to_send'] > 0:
                        msg += f" {result['failed_to_send']} failed."
                    messages.success(request, msg)
                else:
                    messages.error(request, 'SMS sending failed for all recipients.')

        return redirect('core:communication')


class CommunicationBatchGuardiansView(View):
    """JSON endpoint: guardians (deduplicated) linked to students in a given batch."""

    def get(self, request, *args, **kwargs):
        tenant = getattr(request, 'tenant', None)
        batch_id = request.GET.get('batch_id')

        if not tenant or not batch_id:
            return JsonResponse({'error': 'Missing batch_id'}, status=400)

        service = CommunicationService(tenant)
        guardians = service.get_batch_guardians(batch_id)
        return JsonResponse({'guardians': guardians})

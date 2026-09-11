from typing import Dict, Any
from decimal import Decimal
from datetime import date, timedelta
from django.db import transaction
from django.db.models import Q, QuerySet, Count, F, Sum

from core.models import Book, BookCategory, BookMovement, Student, Employee, Library, LibraryStaff
from .base import TenantAwareService
from .exceptions import (
    ValidationException,
    NotFoundException,
    DuplicateException,
    BusinessLogicException,
    ServiceException,
)
from .logging_service import ServiceLogger, logged_operation


class LibraryService(TenantAwareService[Book]):    
    def __init__(self, tenant):
        super().__init__(Book, tenant)
        self.logger = ServiceLogger('library', tenant)
    
    @logged_operation(action='create', resource_type='book', log_result=True)
    def create_book(
        self,
        title: str,
        author: str,
        book_number: str,
        category_id: str,
        isbn: str = None,
        location: str = None,
        total_copies: int = 1,
        price: Decimal = None,
        book_type: str = "OTHER",
        school_level: str = "ALL",
        library_id: str = None,
        user=None,
        **additional_data
    ) -> Book:
        if self.exists(book_number=book_number):
            raise DuplicateException(
                f"Book with number '{book_number}' already exists",
                details={"book_number": book_number}
            )

        category = self._get_book_category_by_id(category_id)
        library = None
        if library_id:
            library = self._get_library_by_id(library_id)

        if total_copies <= 0:
            raise ValidationException(
                "Total copies must be positive",
                details={"total_copies": total_copies}
            )

        book_data = {
            "title": title,
            "author": author,
            "book_number": book_number,
            "category": category,
            "isbn": isbn,
            "location": location,
            "total_copies": total_copies,
            "available_copies": total_copies,
            "price": price,
            "book_type": book_type,
            "school_level": school_level,
            "tenant": self.tenant,
            **additional_data
        }

        if library:
            book_data["library"] = library

        book = Book.objects.create(**book_data)

        self.logger.log_create(
            resource_type='book',
            resource_id=str(book.id),
            user=user,
            details={
                'title': title,
                'author': author,
                'book_number': book_number,
                'category': category.name,
                'isbn': isbn,
                'total_copies': total_copies,
                'book_type': book_type,
                'school_level': school_level,
                'library': library.name if library else None
            }
        )

        return book
    
    def get_book_by_number(self, book_number: str) -> Book:
        book = self.get_or_none(book_number=book_number)
        if book is None:
            raise NotFoundException(
                f"Book with number '{book_number}' not found",
                details={"book_number": book_number}
            )
        return book

    def get_book_by_barcode(self, barcode: str) -> Book:
        book = self.get_or_none(barcode=barcode)
        if book is None:
            raise NotFoundException(
                f"No book found for barcode '{barcode}'",
                details={"barcode": barcode}
            )
        return book
    
    def search_books(
        self,
        query: str,
        category_id: str = None,
        library_id: str = None,
        available_only: bool = False,
        limit: int = None
    ) -> QuerySet[Book]:
        search_filter = (
            Q(title__icontains=query) |
            Q(author__icontains=query) |
            Q(isbn__icontains=query) |
            Q(book_number__icontains=query)
        )

        if category_id:
            search_filter &= Q(category_id=category_id)

        if library_id:
            search_filter &= Q(library_id=library_id)

        if available_only:
            search_filter &= Q(available_copies__gt=0)

        queryset = self.filter(search_filter)

        if limit:
            queryset = queryset[:limit]

        return queryset
    
    def get_books_by_category(self, category_id: str, library_id: str = None) -> QuerySet[Book]:
        filters = Q(category_id=category_id)
        if library_id:
            filters &= Q(library_id=library_id)
        return self.filter(filters)

    def get_available_books(self, library_id: str = None) -> QuerySet[Book]:
        filters = Q(available_copies__gt=0)
        if library_id:
            filters &= Q(library_id=library_id)
        return self.filter(filters)

    def get_books(self, library_id: str = None) -> QuerySet[Book]:
        if library_id:
            return self.filter(library_id=library_id)
        return self.get_base_queryset()
    
    def update_book_copies(self, book_id: str, total_copies: int) -> Book:
        if total_copies <= 0:
            raise ValidationException(
                "Total copies must be positive",
                details={"total_copies": total_copies}
            )
        
        book = self.get_by_id(book_id)
        issued_copies = book.total_copies - book.available_copies
        
        if total_copies < issued_copies:
            raise BusinessLogicException(
                f"Cannot reduce total copies below issued copies ({issued_copies})",
                details={"total_copies": total_copies, "issued_copies": issued_copies}
            )
        
        available_copies = total_copies - issued_copies
        
        return self.update(book_id, total_copies=total_copies, available_copies=available_copies)
    
    def create_book_category(
        self,
        name: str,
        **additional_data
    ) -> BookCategory:
        if BookCategory.objects.filter(
            name=name,
            tenant=self.tenant,
            is_deleted=False
        ).exists():
            raise DuplicateException(
                f"Book category '{name}' already exists",
                details={"name": name}
            )
        
        category_data = {
            "name": name,
            "tenant": self.tenant,
            **additional_data
        }
        
        return BookCategory.objects.create(**category_data)
    
    def get_book_categories(self, active_only: bool = True) -> QuerySet[BookCategory]:
        query = Q(tenant=self.tenant)
        
        if active_only:
            query &= Q(is_deleted=False)
        
        return BookCategory.objects.filter(query)
    
    @logged_operation(action='issue', resource_type='book', log_result=True)
    @transaction.atomic
    def issue_book(
        self,
        book_id: str,
        student_id: str = None,
        employee_id: str = None,
        issue_date: date = None,
        due_date: date = None,
        default_loan_days: int = 14,
        user=None
    ) -> BookMovement:
        if issue_date is None:
            issue_date = date.today()
        
        if due_date is None:
            due_date = issue_date + timedelta(days=default_loan_days)
        
        if not student_id and not employee_id:
            raise ValidationException(
                "Either student_id or employee_id must be provided",
                details={"student_id": student_id, "employee_id": employee_id}
            )
        
        if student_id and employee_id:
            raise ValidationException(
                "Cannot specify both student_id and employee_id",
                details={"student_id": student_id, "employee_id": employee_id}
            )
        
        book = Book.objects.select_for_update().get(id=book_id, tenant=self.tenant)
        if book.available_copies <= 0:
            raise BusinessLogicException(
                f"Book '{book.title}' is not available for issue",
                details={"book_id": book_id, "available_copies": book.available_copies}
            )
        
        student = None
        employee = None
        if student_id:
            student = self._get_student_by_id(student_id)
        if employee_id:
            employee = self._get_employee_by_id(employee_id)
        
        movement_data = {
            "book": book,
            "student": student,
            "employee": employee,
            "issue_date": issue_date,
            "due_date": due_date,
            "tenant": self.tenant
        }
        
        movement = BookMovement.objects.create(**movement_data)
        
        book.available_copies = F('available_copies') - 1
        book.save(update_fields=['available_copies'])
        
        borrower_name = (
            f"{student.first_name} {student.last_name}" if student 
            else f"{employee.first_name} {employee.last_name}"
        )
        
        self.logger.log_create(
            resource_type='book_issue',
            resource_id=str(movement.id),
            user=user,
            details={
                'book': book.title,
                'book_number': book.book_number,
                'borrower': borrower_name,
                'borrower_type': 'student' if student else 'employee',
                'issue_date': str(issue_date),
                'due_date': str(due_date)
            }
        )
        
        return movement

    def issue_book_by_scan(self, barcode: str, student_id=None, employee_id=None, **kwargs) -> BookMovement:
        book = self.get_book_by_barcode(barcode)
        return self.issue_book(book.id, student_id=student_id, employee_id=employee_id, **kwargs)

    def return_book_by_scan(self, barcode: str, return_date: date = None) -> BookMovement:
        book = self.get_book_by_barcode(barcode)
        movement = BookMovement.objects.filter(
            tenant=self.tenant, book=book, is_returned=False
        ).order_by('-issue_date').first()
        if movement is None:
            raise NotFoundException(
                f"No active loan found for book '{book.title}'",
                details={"barcode": barcode}
            )
        return self.return_book(movement.id, return_date)
        
    @transaction.atomic
    def return_book(
        self,
        movement_id: str,
        return_date: date = None
    ) -> BookMovement:
        if return_date is None:
            return_date = date.today()
        
        try:
            movement = BookMovement.objects.get(
                id=movement_id,
                tenant=self.tenant
            )
        except BookMovement.DoesNotExist:
            raise NotFoundException(
                f"Book movement with id {movement_id} not found",
                details={"movement_id": movement_id}
            )
        
        if movement.is_returned:
            raise BusinessLogicException(
                "Book has already been returned",
                details={"movement_id": movement_id, "return_date": movement.return_date}
            )
        
        movement.return_date = return_date
        movement.is_returned = True
        movement.save()
        
        book = movement.book
        book.available_copies = F('available_copies') + 1
        book.save(update_fields=['available_copies'])
        
        return movement
    
    def get_issued_books(
        self,
        student_id: str = None,
        employee_id: str = None,
        library_id: str = None,
        overdue_only: bool = False
    ) -> QuerySet[BookMovement]:
        query = Q(tenant=self.tenant, is_returned=False)

        if student_id:
            query &= Q(student_id=student_id)

        if employee_id:
            query &= Q(employee_id=employee_id)

        if library_id:
            query &= Q(book__library_id=library_id)

        if overdue_only:
            query &= Q(due_date__lt=date.today())

        return BookMovement.objects.filter(query).order_by('due_date')
    
    def get_overdue_books(self, library_id: str = None) -> QuerySet[BookMovement]:
        query = Q(tenant=self.tenant, is_returned=False, due_date__lt=date.today())
        if library_id:
            query &= Q(book__library_id=library_id)
        return BookMovement.objects.filter(query).order_by('due_date')
    
    def get_book_history(self, book_id: str) -> QuerySet[BookMovement]:
        return BookMovement.objects.filter(
            book_id=book_id,
            tenant=self.tenant
        ).order_by('-issue_date')
    
    def get_borrower_history(
        self, 
        student_id: str = None, 
        employee_id: str = None
    ) -> QuerySet[BookMovement]:
        query = Q(tenant=self.tenant)
        
        if student_id:
            query &= Q(student_id=student_id)
        elif employee_id:
            query &= Q(employee_id=employee_id)
        else:
            raise ValidationException(
                "Either student_id or employee_id must be provided"
            )
        
        return BookMovement.objects.filter(query).order_by('-issue_date')
    
    def get_library_statistics(self, library_id: str = None) -> Dict[str, Any]:
        query = Q(tenant=self.tenant)
        if library_id:
            query &= Q(library_id=library_id)

        total_books = Book.objects.filter(query).count()
        total_copies = Book.objects.filter(query).aggregate(
            total=Sum('total_copies'))['total'] or 0
        available_copies = Book.objects.filter(query).aggregate(
            total=Sum('available_copies'))['total'] or 0

        issued_copies = total_copies - available_copies

        total_categories = BookCategory.objects.filter(
            tenant=self.tenant,
            is_deleted=False
        ).count()

        movement_query = Q(tenant=self.tenant)
        if library_id:
            movement_query &= Q(book__library_id=library_id)

        total_issues = BookMovement.objects.filter(movement_query).count()

        active_issues = BookMovement.objects.filter(
            movement_query, is_returned=False
        ).count()

        overdue_books = BookMovement.objects.filter(
            movement_query, is_returned=False, due_date__lt=date.today()
        ).count()

        return {
            'total_books': total_books,
            'total_copies': total_copies,
            'available_copies': available_copies,
            'issued_copies': issued_copies,
            'total_categories': total_categories,
            'total_issues': total_issues,
            'active_issues': active_issues,
            'overdue_books': overdue_books,
            'utilization_rate': round((issued_copies / total_copies * 100), 2) if total_copies > 0 else 0
        }
    
    def get_popular_books(self, library_id: str = None, limit: int = 10) -> QuerySet[Book]:
        query = Q(tenant=self.tenant)
        if library_id:
            query &= Q(library_id=library_id)
        return Book.objects.filter(query).annotate(
            issue_count=Count('movements')
        ).order_by('-issue_count')[:limit]
    
    def get_category_usage_report(self, library_id: str = None) -> QuerySet[BookCategory]:
        query = Q(tenant=self.tenant, is_deleted=False)
        if library_id:
            query &= Q(book__library_id=library_id)
        return BookCategory.objects.filter(query).annotate(
            book_count=Count('book'),
            issue_count=Count('book__movements')
        ).order_by('-issue_count').distinct()
    
    def get_libraries(self, active_only: bool = True) -> QuerySet[Library]:
        query = Q(tenant=self.tenant)
        if active_only:
            query &= Q(is_active=True)
        return Library.objects.filter(query).order_by('name')

    @logged_operation(action='create', resource_type='library')
    def create_library(
        self,
        name: str,
        code: str = None,
        description: str = None,
        **additional_data
    ) -> Library:
        if Library.objects.filter(tenant=self.tenant, name=name).exists():
            raise DuplicateException(
                f"Library '{name}' already exists",
                details={"name": name}
            )

        library = Library.objects.create(
            tenant=self.tenant,
            name=name,
            code=code,
            description=description,
            **additional_data
        )
        return library

    @logged_operation(action='assign', resource_type='librarian_staff')
    def assign_librarian(self, employee_id: str, library_id: str) -> LibraryStaff:
        employee = self._get_employee_by_id(employee_id)
        library = self._get_library_by_id(library_id)

        assignment, created = LibraryStaff.objects.get_or_create(
            tenant=self.tenant,
            employee=employee,
            library=library,
            defaults={'is_active': True}
        )

        if not created and not assignment.is_active:
            assignment.is_active = True
            assignment.save()

        return assignment

    @logged_operation(action='unassign', resource_type='librarian_staff')
    def unassign_librarian(self, employee_id: str, library_id: str) -> None:
        try:
            assignment = LibraryStaff.objects.get(
                tenant=self.tenant,
                employee_id=employee_id,
                library_id=library_id
            )
            assignment.delete()
        except LibraryStaff.DoesNotExist:
            raise NotFoundException(
                f"Librarian assignment not found",
                details={"employee_id": employee_id, "library_id": library_id}
            )

    def _get_library_by_id(self, library_id: str) -> Library:
        try:
            return Library.objects.get(
                id=library_id,
                tenant=self.tenant
            )
        except Library.DoesNotExist:
            raise NotFoundException(
                f"Library with id {library_id} not found",
                details={"library_id": library_id}
            )

    def _get_book_category_by_id(self, category_id: str) -> BookCategory:
        try:
            return BookCategory.objects.get(
                id=category_id,
                tenant=self.tenant,
                is_deleted=False
            )
        except BookCategory.DoesNotExist:
            raise NotFoundException(
                f"Book category with id {category_id} not found",
                details={"category_id": category_id}
            )
    
    def _get_student_by_id(self, student_id: str) -> Student:
        try:
            return Student.objects.get(
                id=student_id,
                tenant=self.tenant,
                is_active=True
            )
        except Student.DoesNotExist:
            raise NotFoundException(
                f"Student with id {student_id} not found",
                details={"student_id": student_id}
            )
    
    def _get_employee_by_id(self, employee_id: str) -> Employee:
        try:
            return Employee.objects.get(
                id=employee_id,
                tenant=self.tenant,
                status=True
            )
        except Employee.DoesNotExist:
            raise NotFoundException(
                f"Employee with id {employee_id} not found",
                details={"employee_id": employee_id}
            )
    
    def _validate_create_data(self, data: Dict[str, Any]) -> None:
        super()._validate_create_data(data)
        
        required_fields = ['title', 'author', 'book_number', 'category']
        for field in required_fields:
            if field not in data or not data[field]:
                raise ValidationException(
                    f"Required field '{field}' is missing or empty",
                    details={"field": field}
                )
        
        total_copies = data.get('total_copies', 1)
        if total_copies <= 0:
            raise ValidationException(
                "Total copies must be positive",
                details={"total_copies": total_copies}
            )
        
        price = data.get('price')
        if price is not None and price < 0:
            raise ValidationException(
                "Price cannot be negative",
                details={"price": price}
            )
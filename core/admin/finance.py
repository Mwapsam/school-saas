from django.contrib import admin
from django.utils.html import format_html
from unfold.admin import ModelAdmin, TabularInline
from core.models import (
    FeeCategory, FeeParticular, FamilyInvoice, FamilyInvoiceLine,
    FeeTransaction, FinanceFee, Guardian, FeeCollection, FeeDiscount,
    FineSlab, FinanceTransaction, FinanceTransactionCategory,
    FeeMasterParticular, FeeMasterDiscount, FeeApplicabilityRule,
    StudentGuardianRelation,
)

class FeeParticularInline(TabularInline):
    model = FeeParticular
    extra = 1
    fields = ("name", "amount", "due_date", "fine_slab")

class StudentGuardianRelationInline(TabularInline):
    model = StudentGuardianRelation
    fk_name = "guardian"
    extra = 0
    fields = ("student", "relation", "is_immediate_contact")
    raw_id_fields = ("student",)

@admin.register(Guardian)
class GuardianAdmin(ModelAdmin):
    list_display = ("first_name", "last_name", "email", "mobile_phone", "linked_students")
    list_filter = ("is_active",)
    search_fields = ("first_name", "last_name", "email")
    inlines = [StudentGuardianRelationInline]

    def get_queryset(self, request):
        return super().get_queryset(request).prefetch_related("student_relations__student")

    def save_formset(self, request, form, formset, change):
        """StudentGuardianRelation.tenant/school are required, non-nullable —
        fill them in from the request the same way other tenant-scoped
        admin inlines in this project do (see CourseAdmin.save_model)."""
        instances = formset.save(commit=False)
        tenant = getattr(request, "tenant", None)
        for obj in instances:
            if isinstance(obj, StudentGuardianRelation) and tenant:
                if not obj.tenant_id:
                    obj.tenant = tenant
                if not obj.school_id:
                    obj.school = tenant
            obj.save()
        formset.save_m2m()

    @admin.display(description="Linked Students")
    def linked_students(self, obj):
        names = [
            f"{rel.student.first_name} {rel.student.last_name}"
            for rel in obj.student_relations.all()
        ]
        return ", ".join(names) if names else "—"

@admin.register(FeeCategory)
class FeeCategoryAdmin(ModelAdmin):
    list_display = ("name", "is_deleted")
    list_filter = ("is_deleted",)
    search_fields = ("name",)
    inlines = [FeeParticularInline]

class FamilyInvoiceLineInline(TabularInline):
    model = FamilyInvoiceLine
    extra = 0
    readonly_fields = ("student", "finance_fee", "description", "amount")
    can_delete = False

@admin.register(FamilyInvoice)
class FamilyInvoiceAdmin(ModelAdmin):
    list_display = (
        "invoice_number",
        "guardian",
        "total_amount",
        "amount_paid",
        "balance_due",
        "status_badge",
        "due_date"
    )
    list_filter = ("status", "due_date")
    search_fields = ("invoice_number", "guardian__first_name", "guardian__last_name")
    autocomplete_fields = ("guardian",)
    readonly_fields = ("subtotal", "total_amount", "amount_paid", "balance_due")
    inlines = [FamilyInvoiceLineInline]

    @admin.display(description="Status")
    def status_badge(self, obj):
        colors = {
            "open": "bg-yellow-100 text-yellow-800 dark:bg-yellow-900 dark:text-yellow-300",
            "paid": "bg-green-100 text-green-800 dark:bg-green-900 dark:text-green-300",
            "void": "bg-red-100 text-red-800 dark:bg-red-900 dark:text-red-300",
        }
        classes = colors.get(obj.status, "bg-gray-100 text-gray-800")
        return format_html(
            '<span class="{} px-2 py-1 rounded-full text-xs font-medium">{}</span>',
            classes,
            obj.get_status_display()
        )

@admin.register(FeeTransaction)
class FeeTransactionAdmin(ModelAdmin):
    list_display = ("student", "transaction_type", "amount", "payment_method", "transaction_date")
    list_filter = ("transaction_type", "payment_method", "transaction_date")
    search_fields = ("student__first_name", "student__last_name", "reference_number")
    autocomplete_fields = ("student",)

    date_hierarchy = "transaction_date"


@admin.register(FeeCollection)
class FeeCollectionAdmin(ModelAdmin):
    list_display = ("name", "fee_category", "batch", "due_date", "academic_year", "is_active")
    list_filter = ("is_active", "academic_year")
    search_fields = ("name",)
    autocomplete_fields = ("fee_category", "batch", "academic_year")


@admin.register(FeeDiscount)
class FeeDiscountAdmin(ModelAdmin):
    list_display = ("name", "discount_type", "fee_category", "discount_mode", "discount_value", "is_active")
    list_filter = ("discount_type", "discount_mode", "is_active")
    search_fields = ("name",)
    autocomplete_fields = ("fee_category",)
    filter_horizontal = ("batches", "students")


@admin.register(FineSlab)
class FineSlabAdmin(ModelAdmin):
    list_display = ("fine_name", "days_after_due", "fine_mode", "fine_value", "is_active")
    list_filter = ("fine_mode", "is_active")
    search_fields = ("fine_name",)


@admin.register(FinanceFee)
class FinanceFeeAdmin(ModelAdmin):
    list_display = ("student", "fee_category", "balance", "is_paid", "academic_year", "transaction_date")
    list_filter = ("is_paid", "academic_year")
    search_fields = ("student__first_name", "student__last_name", "student__admission_no")
    autocomplete_fields = ("student", "fee_category", "batch", "academic_year", "fee_collection")


@admin.register(FinanceTransactionCategory)
class FinanceTransactionCategoryAdmin(ModelAdmin):
    list_display = ("name", "prefix", "is_income")
    list_filter = ("is_income",)
    search_fields = ("name",)


@admin.register(FinanceTransaction)
class FinanceTransactionAdmin(ModelAdmin):
    list_display = ("title", "amount", "category", "student", "employee", "transaction_date", "payment_method")
    list_filter = ("category", "payment_method", "academic_year")
    search_fields = ("title", "reference_number")
    autocomplete_fields = ("category", "student", "employee", "academic_year")
    date_hierarchy = "transaction_date"


@admin.register(FeeMasterParticular)
class FeeMasterParticularAdmin(ModelAdmin):
    list_display = ("name", "description", "is_active")
    list_filter = ("is_active",)
    search_fields = ("name",)


@admin.register(FeeMasterDiscount)
class FeeMasterDiscountAdmin(ModelAdmin):
    list_display = ("name", "discount_type", "value", "description", "is_active")
    list_filter = ("discount_type", "is_active")
    search_fields = ("name",)


@admin.register(FeeApplicabilityRule)
class FeeApplicabilityRuleAdmin(ModelAdmin):
    list_display = ("rule_type", "batch", "student_category", "admission_number", "student", "is_active")
    list_filter = ("rule_type", "is_active")
    search_fields = ("admission_number",)
    autocomplete_fields = ("batch", "student_category", "student")
from django.contrib import admin
from .models import (
    Account, Line, Service, LineService, BillingStatement, BillingLineItem,
    SapSalesOrder, SapDelivery, AccountEvent,
)


@admin.register(Account)
class AccountAdmin(admin.ModelAdmin):
    list_display = ['account_number', 'user', 'status', 'account_type', 'number_of_lines', 'created_on']
    list_filter = ['status', 'account_type', 'created_on']
    search_fields = ['account_number', 'user__username']
    readonly_fields = ['number_of_lines']


@admin.register(Line)
class LineAdmin(admin.ModelAdmin):
    list_display = ['line_name', 'msdn', 'employee_name', 'employee_number', 'account', 'status', 'added_on']
    list_filter = ['status', 'account', 'added_on']
    search_fields = ['line_name', 'msdn', 'employee_name', 'employee_number']


@admin.register(Service)
class ServiceAdmin(admin.ModelAdmin):
    list_display = ['name', 'service_type', 'price', 'duration_days', 'data_allowance_mb', 'is_active']
    list_filter = ['service_type', 'is_active', 'created_at']
    search_fields = ['name', 'description']


@admin.register(LineService)
class LineServiceAdmin(admin.ModelAdmin):
    list_display = ['line', 'service', 'status', 'activated_at', 'expires_at', 'total_amount', 'transaction_id']
    list_filter = ['status', 'service', 'activated_at', 'expires_at']
    search_fields = ['line__line_name', 'line__msdn', 'service__name', 'transaction_id']
    readonly_fields = ['total_amount']


class BillingLineItemInline(admin.TabularInline):
    model = BillingLineItem
    extra = 0
    readonly_fields = ['line', 'description', 'category', 'amount']


@admin.register(BillingStatement)
class BillingStatementAdmin(admin.ModelAdmin):
    list_display = [
        'account', 'period_start', 'period_end', 'due_date',
        'total_amount', 'amount_paid', 'status',
    ]
    list_filter = ['status', 'due_date', 'period_start']
    search_fields = ['account__account_number']
    inlines = [BillingLineItemInline]
    readonly_fields = ['subtotal', 'tax_amount', 'total_amount']


@admin.register(BillingLineItem)
class BillingLineItemAdmin(admin.ModelAdmin):
    list_display = ['statement', 'line', 'category', 'description', 'amount']
    list_filter = ['category']
    search_fields = ['description', 'statement__account__account_number']


@admin.register(SapSalesOrder)
class SapSalesOrderAdmin(admin.ModelAdmin):
    list_display = ['sap_order_number', 'account', 'line', 'device_model', 'status', 'ordered_on']
    list_filter = ['status', 'ordered_on']
    search_fields = ['sap_order_number', 'line__msdn', 'line__employee_name', 'device_model']


@admin.register(SapDelivery)
class SapDeliveryAdmin(admin.ModelAdmin):
    list_display = ['order', 'dispatched', 'actual_dispatch_date', 'expected_dispatch_date', 'carrier']
    list_filter = ['dispatched']


@admin.register(AccountEvent)
class AccountEventAdmin(admin.ModelAdmin):
    list_display = ['account', 'occurred_at', 'event_type', 'summary', 'line', 'amount']
    list_filter = ['event_type', 'occurred_at']
    search_fields = ['summary', 'reference', 'account__account_number']

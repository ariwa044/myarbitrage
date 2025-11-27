from django.contrib import admin
from django.utils.html import format_html
from django.urls import reverse, path
from django.db.models import Sum, Count
from django.http import HttpResponseRedirect
from django.shortcuts import get_object_or_404
from .models import Deposit, Withdrawal, Type_plans, Investment, Cryptocurrency

@admin.register(Cryptocurrency)
class CryptocurrencyAdmin(admin.ModelAdmin):
    list_display = ['name', 'symbol', 'deposit_address', 'deposits_count']
    search_fields = ['name', 'symbol']
    readonly_fields = ['deposits_count']
    
    fieldsets = (
        ('Cryptocurrency Information', {
            'fields': ('name', 'symbol', 'deposit_address')
        }),
        ('Statistics', {
            'fields': ('deposits_count',)
        })
    )
    
    def deposits_count(self, obj):
        return obj.deposits.count()
    deposits_count.short_description = 'Total Deposits'

@admin.register(Deposit)
class DepositAdmin(admin.ModelAdmin):
    list_display = ['deposit_id', 'user_email', 'amount', 'crypto_name', 
                   'status', 'created_at']
    list_filter = ['status', 'crypto', 'created_at']
    search_fields = ['deposit_id', 'user__email']
    ordering = ['-created_at']
    readonly_fields = ['deposit_id', 'created_at']
    

    
    def user_email(self, obj):
        return obj.user.email
    user_email.short_description = 'User'
    
    def crypto_name(self, obj):
        return f"{obj.crypto.name} ({obj.crypto.symbol})" if obj.crypto else "N/A"
    crypto_name.short_description = 'Cryptocurrency'
    


@admin.register(Withdrawal)
class WithdrawalAdmin(admin.ModelAdmin):
    list_display = ['withdrawal_id', 'user_email', 'amount', 'crypto_currency', 
                   'wallet_address', 'status', 'created_at']
    list_filter = ['status', 'crypto_currency', 'created_at']
    search_fields = ['withdrawal_id', 'user__email', 'wallet_address']
    readonly_fields = ['withdrawal_id', 'created_at']
    ordering = ['-created_at']
    
    
    def user_email(self, obj):
        return obj.user.email
    user_email.short_description = 'User'
    
 
@admin.register(Type_plans)
class TypePlansAdmin(admin.ModelAdmin):
    list_display = ['name', 'min_amount', 'max_amount', 'percent_return', 
                   'duration_days', 'active_investments_count', 'total_invested']
    search_fields = ['name']
    list_filter = ['duration_days', 'percent_return']
    
    def active_investments_count(self, obj):
        return Investment.objects.filter(type_plan=obj, is_active=True).count()
    active_investments_count.short_description = 'Active Investments'
    
    def total_invested(self, obj):
        total = Investment.objects.filter(type_plan=obj).aggregate(
            total=Sum('amount_invested'))['total']
        return total or 0
    total_invested.short_description = 'Total Invested'


@admin.register(Investment)
class InvestmentAdmin(admin.ModelAdmin):
    list_display = ['user_email', 'amount_invested', 'type_plan', 'plan_id', 'is_active', 'status']
    list_filter = ['is_active', 'status']
    search_fields = ['user__email']
    ordering = ['-start_date']
    
    readonly_fields = ['plan_id']
    
    fieldsets = (
        ('Basic Information', {
            'fields': ('user', 'amount_invested', 'plan_id', 'type_plan', 'is_active', 'status')
        }),
        ('Timestamps & Returns', {
            'fields': ('start_date', 'end_date', 'expected_return', 'profit_made')
        })
    )
    
    def user_email(self, obj):
        return obj.user.email
    user_email.short_description = 'User'


# Custom admin actions
@admin.action(description='Approve selected withdrawals')
def approve_withdrawals(modeladmin, request, queryset):
    queryset.filter(status='PENDING').update(status='COMPLETED')

# Register actions
WithdrawalAdmin.actions = [approve_withdrawals]

# Add admin site customization
admin.site.site_header = 'Investment Platform Administration'
admin.site.site_title = 'Investment Admin Portal'
admin.site.index_title = 'Platform Management'

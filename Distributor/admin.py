from django.contrib import admin
from .models import Distributor, DistributorActivityLog, DistributorPasswordResetOTP

@admin.register(Distributor)
class DistributorAdmin(admin.ModelAdmin):
    list_display = ('distributorid', 'username', 'email', 'phone', 'company_name', 'registration_date', 'is_active')
    search_fields = ('username', 'email', 'phone', 'company_name', 'city', 'state')
    list_filter = ('is_active', 'registration_date', 'state', 'city')
    ordering = ('-registration_date',)
    readonly_fields = ('registration_date', 'last_updated', 'last_login')

@admin.register(DistributorActivityLog)
class DistributorActivityLogAdmin(admin.ModelAdmin):
    list_display = ('email', 'action', 'ip_address', 'user_agent', 'created_at')
    list_filter = ('action', 'created_at')
    search_fields = ('email', 'action', 'ip_address')
    ordering = ('-created_at',)
    readonly_fields = ('created_at',)

@admin.register(DistributorPasswordResetOTP)
class DistributorPasswordResetOTPAdmin(admin.ModelAdmin):
    list_display = ('email', 'is_used', 'created_at', 'expires_at')
    list_filter = ('is_used', 'created_at', 'expires_at')
    search_fields = ('email',)
    ordering = ('-created_at',)
    readonly_fields = ('created_at',)
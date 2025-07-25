from django.contrib import admin
from .models import License, LicenseValidation

@admin.register(License)
class LicenseAdmin(admin.ModelAdmin):
    list_display = ['user', 'license_key', 'is_active', 'usage_count', 'created_at']
    list_filter = ['is_active', 'hardware_bound', 'created_at']
    search_fields = ['user__email', 'license_key']
    readonly_fields = ['license_key', 'created_at', 'last_validated']
    ordering = ['-created_at']

@admin.register(LicenseValidation)
class LicenseValidationAdmin(admin.ModelAdmin):
    list_display = ['license', 'hardware_fingerprint', 'ip_address', 'is_successful', 'validated_at']
    list_filter = ['is_successful', 'validated_at']
    search_fields = ['license__user__email', 'hardware_fingerprint', 'ip_address']
    readonly_fields = ['validated_at']
    ordering = ['-validated_at']
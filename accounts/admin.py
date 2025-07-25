from django.contrib import admin
from django.contrib.auth.admin import UserAdmin as BaseUserAdmin
from .models import User

@admin.register(User)
class UserAdmin(BaseUserAdmin):
    list_display = ['email', 'username', 'subscription_plan', 'created_at', 'is_active']
    list_filter = ['subscription_plan', 'is_active', 'created_at']
    search_fields = ['email', 'username']
    ordering = ['-created_at']
    
    fieldsets = BaseUserAdmin.fieldsets + (
        ('TikTrue Settings', {
            'fields': ('subscription_plan', 'subscription_expires', 'hardware_fingerprint', 
                      'max_clients', 'allowed_models')
        }),
    )
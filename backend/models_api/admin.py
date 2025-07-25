from django.contrib import admin
from .models import ModelFile, ModelAccess, ModelDownload

@admin.register(ModelFile)
class ModelFileAdmin(admin.ModelAdmin):
    list_display = ['display_name', 'name', 'version', 'file_size', 'block_count', 'is_active']
    list_filter = ['is_active', 'created_at']
    search_fields = ['name', 'display_name']
    readonly_fields = ['created_at', 'updated_at']

@admin.register(ModelAccess)
class ModelAccessAdmin(admin.ModelAdmin):
    list_display = ['user', 'model', 'access_granted', 'download_count', 'last_download']
    list_filter = ['access_granted', 'created_at', 'last_download']
    search_fields = ['user__email', 'model__name']
    readonly_fields = ['created_at']

@admin.register(ModelDownload)
class ModelDownloadAdmin(admin.ModelAdmin):
    list_display = ['user', 'model', 'is_completed', 'started_at', 'completed_at']
    list_filter = ['is_completed', 'started_at']
    search_fields = ['user__email', 'model__name', 'download_token']
    readonly_fields = ['download_token', 'started_at', 'completed_at']
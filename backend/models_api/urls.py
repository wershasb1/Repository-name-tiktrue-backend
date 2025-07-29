from django.urls import path
from . import views

urlpatterns = [
    # Model listing and metadata
    path('available/', views.available_models, name='available_models'),
    path('<uuid:model_id>/metadata/', views.model_metadata, name='model_metadata'),
    
    # Download management
    path('<uuid:model_id>/download/', views.create_download_token, name='create_download_token'),
    path('download/<str:download_token>/', views.download_model, name='download_model'),
    path('download/<str:download_token>/block/<int:block_id>/', views.download_model_block, name='download_model_block'),
    path('download/<str:download_token>/metadata/', views.download_model_metadata, name='download_model_metadata'),
    path('download/<str:download_token>/tokenizer/', views.download_model_tokenizer, name='download_model_tokenizer'),
    path('download/<str:download_token>/complete/', views.record_download_completion, name='record_download_completion'),
    
    # Storage management
    path('<uuid:model_id>/storage-stats/', views.model_storage_stats, name='model_storage_stats'),
    path('<uuid:model_id>/verify-integrity/', views.verify_model_integrity, name='verify_model_integrity'),
    
    # Access control
    path('<uuid:model_id>/check-access/', views.check_model_access, name='check_model_access'),
    path('access/summary/', views.user_access_summary, name='user_access_summary'),
    path('access/limits/', views.subscription_limits, name='subscription_limits'),
    path('access/validate-bulk/', views.validate_bulk_access, name='validate_bulk_access'),
    
    # Analytics
    path('analytics/user/', views.user_usage_analytics, name='user_usage_analytics'),
    path('<uuid:model_id>/analytics/', views.model_usage_analytics, name='model_usage_analytics'),
    path('analytics/system/', views.system_usage_overview, name='system_usage_overview'),
]
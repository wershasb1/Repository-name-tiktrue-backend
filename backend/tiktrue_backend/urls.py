"""
URL configuration for tiktrue_backend project.
"""
from django.contrib import admin
from django.urls import path, include
from django.conf import settings
from django.conf.urls.static import static
from .setup_views import setup_database, health_check
from models_api.views import get_desktop_app_info, download_desktop_app, installation_guide

urlpatterns = [
    path('admin/', admin.site.urls),
    path('api/v1/auth/', include('accounts.urls')),
    path('api/v1/license/', include('licenses.urls')),
    path('api/v1/models/', include('models_api.urls')),
    path('api/v1/payments/', include('payments.urls')),
    # Desktop app download endpoints
    path('api/v1/downloads/desktop-app-info/', get_desktop_app_info, name='desktop_app_info'),
    path('api/v1/downloads/desktop-app/<str:filename>', download_desktop_app, name='download_desktop_app'),
    path('api/v1/downloads/installation-guide/', installation_guide, name='installation_guide'),
    # Setup endpoints
    path('setup/database/', setup_database, name='setup_database'),
    path('health/', health_check, name='health_check'),
]

# Serve media files in development
if settings.DEBUG:
    urlpatterns += static(settings.MEDIA_URL, document_root=settings.MEDIA_ROOT)
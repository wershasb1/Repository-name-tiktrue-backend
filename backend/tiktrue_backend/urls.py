"""
URL configuration for tiktrue_backend project.
"""
from django.contrib import admin
from django.urls import path, include
from django.conf import settings
from django.conf.urls.static import static
from .setup_views import setup_database, health_check

urlpatterns = [
    path('admin/', admin.site.urls),
    path('api/v1/auth/', include('accounts.urls')),
    path('api/v1/license/', include('licenses.urls')),
    path('api/v1/models/', include('models_api.urls')),
    # Setup endpoints
    path('setup/database/', setup_database, name='setup_database'),
    path('health/', health_check, name='health_check'),
]

# Serve media files in development
if settings.DEBUG:
    urlpatterns += static(settings.MEDIA_URL, document_root=settings.MEDIA_ROOT)
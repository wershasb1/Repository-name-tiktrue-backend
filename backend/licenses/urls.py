from django.urls import path
from . import views

urlpatterns = [
    path('validate/', views.validate_license, name='validate_license'),
    path('info/', views.license_info, name='license_info'),
]
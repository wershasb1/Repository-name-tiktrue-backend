from django.urls import path
from . import views

urlpatterns = [
    path('available/', views.available_models, name='available_models'),
    path('<uuid:model_id>/metadata/', views.model_metadata, name='model_metadata'),
    path('<uuid:model_id>/download/', views.create_download_token, name='create_download_token'),
    path('download/<str:download_token>/', views.download_model, name='download_model'),
]
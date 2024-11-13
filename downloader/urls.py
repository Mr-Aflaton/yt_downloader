# urls.py
from django.urls import path
from . import views

urlpatterns = [
    path('', views.process_url, name='index'),
    path('download/', views.download_vid, name='download'),
]
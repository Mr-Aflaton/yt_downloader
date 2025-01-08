
from django.urls import path
from . import views

urlpatterns = [
    path('', views.process_url, name='index'),
    path('download/', views.download_vid, name='download'),
    path('download-playlist/', views.download_playlist, name='download_playlist'),
    path('check-progress/', views.check_download_progress, name='check_progress'),
    path('download-zip/<str:filename>/', views.download_zip, name='download_zip'),
    path('check-video-progress/', views.check_video_progress, name='check_video_progress'),
    path('start-download/', views.start_download, name='start_download'),
    path('get-download-file/', views.get_download_file, name='get_download_file'),
]
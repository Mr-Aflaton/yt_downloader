
import os
import shutil
import tempfile
import zipfile
from datetime import datetime
from django.utils import timezone
from django.core.paginator import Paginator
from django.http import FileResponse, HttpRequest, HttpResponse
from django.shortcuts import render, redirect
from django.contrib import messages
from django.urls import reverse
from django.conf import settings

from . import utils
from .models import VideoHistory, PlaylistVideo


from django.http import JsonResponse
from django.views.decorators.csrf import csrf_exempt
import json
import threading
import queue


download_progress = {}

def start_playlist_download(playlist_id, format_type, temp_dir):
    """Background task for downloading playlist"""
    global download_progress
    
    videos = PlaylistVideo.objects.filter(playlist_id=playlist_id)
    total_videos = videos.count()
    download_progress[playlist_id] = {
        'current': 0,
        'total': total_videos,
        'status': 'downloading',
        'completed_videos': [],
        'failed_videos': []
    }
    
    try:
        for video in videos:
            video_details = utils.extract_video_info(video.url)
            if not video_details or not video_details['formats']:
                download_progress[playlist_id]['failed_videos'].append(video.title)
                continue
            
            
            selected_format = None
            for fmt in video_details['formats']:
                if format_type == 'audio' and fmt['type'] == 'audio':
                    selected_format = fmt
                    
                    selected_format['audio_format_id'] = None
                    break
                elif format_type == 'video' and fmt['type'] == 'video':
                    selected_format = fmt
                    break
            
            if not selected_format:
                download_progress[playlist_id]['failed_videos'].append(video.title)
                continue
            
            
            video_path, audio_path = utils.download_video(
                video.url,
                selected_format['format_id'],
                temp_dir,
                selected_format.get('audio_format_id')  
            )
            
            if video_path:
                
                if format_type == 'video' and audio_path and os.path.exists(audio_path):
                    output_path = os.path.join(temp_dir, f"{os.path.basename(video_path)}")
                    if utils.merge_video_audio(video_path, audio_path, output_path, playlist_id):
                        os.remove(video_path)
                        os.remove(audio_path)
                
                download_progress[playlist_id]['completed_videos'].append(video.title)
            else:
                download_progress[playlist_id]['failed_videos'].append(video.title)
            
            download_progress[playlist_id]['current'] += 1
        
        
        zip_filename = os.path.join(TEMP_DIR, f'playlist_{datetime.now().strftime("%Y%m%d_%H%M%S")}.zip')
        with zipfile.ZipFile(zip_filename, 'w') as zip_file:
            for root, dirs, files in os.walk(temp_dir):
                for file in files:
                    file_path = os.path.join(root, file)
                    zip_file.write(file_path, os.path.basename(file_path))
        
        download_progress[playlist_id]['status'] = 'completed'
        download_progress[playlist_id]['zip_file'] = zip_filename
        
    except Exception as e:
        print(f"Error in background download: {e}")
        download_progress[playlist_id]['status'] = 'failed'
    finally:
        if os.path.exists(temp_dir):
            shutil.rmtree(temp_dir)

@csrf_exempt
def check_download_progress(request):
    """API endpoint to check download progress"""
    if request.method == 'POST':
        data = json.loads(request.body)
        playlist_id = data.get('playlist_id')
        
        if playlist_id in download_progress:
            progress = download_progress[playlist_id]
            
            
            if progress['status'] == 'completed':
                zip_path = progress.get('zip_file')
                if zip_path and os.path.exists(zip_path):
                    progress['download_url'] = reverse('download_zip', args=[os.path.basename(zip_path)])
            
            return JsonResponse(progress)
    
    return JsonResponse({'error': 'Invalid request'}, status=400)

def download_zip(request, filename):
    """Download the completed ZIP file"""
    file_path = os.path.join(TEMP_DIR, filename)
    if os.path.exists(file_path):
        response = FileResponse(
            open(file_path, 'rb'),
            as_attachment=True,
            filename=filename
        )
        response['Content-Length'] = os.path.getsize(file_path)
        return response
    return HttpResponse('File not found', status=404)

def download_playlist(request: HttpRequest) -> HttpResponse:
    """
    Start playlist download in background
    """
    if request.method != 'POST':
        return redirect('index')
    
    playlist_id = request.POST.get('playlist_id')
    format_type = request.POST.get('format_type', 'video')
    
    if not playlist_id:
        return JsonResponse({'error': 'Missing playlist ID'}, status=400)
    
    videos = PlaylistVideo.objects.filter(playlist_id=playlist_id)
    if not videos.exists():
        return JsonResponse({'error': 'No videos found in playlist'}, status=400)
    
    
    playlist_temp_dir = os.path.join(TEMP_DIR, f'playlist_{datetime.now().strftime("%Y%m%d_%H%M%S")}')
    os.makedirs(playlist_temp_dir, exist_ok=True)
    
    
    thread = threading.Thread(
        target=start_playlist_download,
        args=(playlist_id, format_type, playlist_temp_dir)
    )
    thread.start()
    
    return JsonResponse({
        'status': 'started',
        'message': 'Download started'
    })



TEMP_DIR = os.path.join(settings.BASE_DIR, 'temp_downloads')
os.makedirs(TEMP_DIR, exist_ok=True)

def process_url(request: HttpRequest) -> HttpResponse:
    """
    Process YouTube URL for both single videos and playlists.
    Handles history tracking and format extraction.
    """
    context = {}
    
    
    history_list = VideoHistory.objects.all()
    paginator = Paginator(history_list, 10)
    page = request.GET.get('page')
    context['history'] = paginator.get_page(page)
    
    
    url = request.GET.get('url')
    if url:
        request.method = 'POST'
        request.POST = request.POST.copy()
        request.POST['url'] = url
    
    if request.method == 'POST':
        url = request.POST.get('url')
        
        
        url_validation = utils.validate_youtube_url(url)
        if url_validation is not True:
            messages.error(request, f"Invalid URL: {url_validation}")
            return render(request, 'downloader/index.html', context)
        
        
        if utils.is_playlist_url(url):
            playlist_details = utils.extract_playlist_info(url)
            print(playlist_details)
            if not playlist_details:
                messages.error(request, "Failed to extract playlist information")
                return render(request, 'downloader/index.html', context)
            
            
            PlaylistVideo.objects.filter(playlist_id=url).delete()
            for video in playlist_details['videos']:
                PlaylistVideo.objects.create(
                    playlist_id=url,
                    title=video['title'],
                    url=video['url'],
                    thumbnail=video['thumbnail'],
                    position=video['position']
                )
            
            context['playlist'] = playlist_details
            context['playlist_id'] = url
            
        
        else:
            video_details = utils.extract_video_info(url)
            if not video_details:
                messages.error(request, "Failed to extract video information")
                return render(request, 'downloader/index.html', context)
            
            
            existing_video = VideoHistory.objects.filter(url=url).first()
            if existing_video:
                
                existing_video.lookup_date = timezone.now()
                existing_video.save()
            else:
                
                VideoHistory.objects.create(
                    title=video_details['title'],
                    url=url,
                    thumbnail=video_details['thumbnail']
                )
            
            context.update(video_details)
    
    return render(request, 'downloader/index.html', context)

def download_vid(request: HttpRequest) -> FileResponse:
    """
    Handle single video download requests.
    Supports both video and audio downloads.
    """
    
    for file in os.listdir(TEMP_DIR):
        file_path = os.path.join(TEMP_DIR, file)
        try:
            if os.path.isfile(file_path):
                os.unlink(file_path)
            elif os.path.isdir(file_path):
                shutil.rmtree(file_path)
        except Exception as e:
            print(f"Error cleaning temporary files: {e}")
    
    if request.method != 'POST':
        return redirect('index')
    
    url = request.POST.get('url')
    format_id = request.POST.get('format_id')
    
    if not url or not format_id:
        messages.error(request, "Missing URL or format selection")
        return redirect('index')
    
    
    video_format_id = format_id.split('+')[0]
    audio_format_id = format_id.split('+')[1] if '+' in format_id else None
    
    
    video_path, audio_path = utils.download_video(
        url, video_format_id, TEMP_DIR, audio_format_id
    )
    
    if not video_path or not os.path.exists(video_path):
        messages.error(request, "Download failed")
        return redirect('index')
    
    try:
        output_filename = os.path.basename(video_path)
        
        
        if audio_path and os.path.exists(audio_path):
            output_path = os.path.join(TEMP_DIR, f"{output_filename}")
            download_id = f"{url}_{format_id}"  
            if utils.merge_video_audio(video_path, audio_path, output_path, download_id):
                video_path = output_path
                output_filename = os.path.basename(output_path)
        
        
        response = FileResponse(
            open(video_path, 'rb'),
            as_attachment=True,
            filename=output_filename
        )
        response['Content-Length'] = os.path.getsize(video_path)
        return response
    
    except Exception as e:
        print(f"Error serving file: {e}")
        messages.error(request, "Error processing download")
        return redirect('index')

@csrf_exempt
def check_video_progress(request):
    """API endpoint to check individual video download progress"""
    if request.method == 'POST':
        data = json.loads(request.body)
        download_id = data.get('download_id')
        print(utils.download_progress)
        if download_id in utils.download_progress:  
            return JsonResponse(utils.download_progress[download_id])
    
    return JsonResponse({'status': 'not_found'})







@csrf_exempt
def start_download(request: HttpRequest) -> HttpResponse:
    """Initiate the download process"""
    if request.method == 'POST':
        url = request.POST.get('url')
        format_id = request.POST.get('format_id')
        print(request.POST)
        
        if not url or not format_id:
            return JsonResponse({'error': 'Missing URL or format selection'}, status=400)
        
        
        download_id = f"{url}_{format_id}+"
        
        
        thread = threading.Thread(
            target=process_download,
            args=(url, format_id, download_id)
        )
        thread.start()
        
        return JsonResponse({
            'status': 'started',
            'download_id': download_id
        })
    
    return JsonResponse({'error': 'Invalid request'}, status=400)

def process_download(url: str, format_id: str, download_id: str):
    """Process the download in background"""
    try:
        
        for file in os.listdir(TEMP_DIR):
            file_path = os.path.join(TEMP_DIR, file)
            try:
                if os.path.isfile(file_path):
                    os.unlink(file_path)
                elif os.path.isdir(file_path):
                    shutil.rmtree(file_path)
            except Exception as e:
                print(f"Error cleaning temporary files: {e}")
        
        
        video_format_id = format_id.split('+')[0]
        audio_format_id = format_id.split('+')[1] if '+' in format_id else None
        
        
        video_path, audio_path = utils.download_video(
            url, video_format_id, TEMP_DIR, audio_format_id
        )
        
        if not video_path or not os.path.exists(video_path):
            utils.download_progress[download_id] = {
                'status': 'error',
                'error': 'Download failed'
            }
            return
        
        try:
            output_filename = os.path.basename(video_path)
            
            
            if audio_path and os.path.exists(audio_path) and audio_format_id:
                output_path = os.path.join(TEMP_DIR, f"{output_filename}")
                if utils.merge_video_audio(video_path, audio_path, output_path, download_id):
                    os.remove(video_path)
                    os.remove(audio_path)
                    video_path = output_path
                    output_filename = os.path.basename(output_path)
            
            utils.download_progress[download_id] = {
                'status': 'completed',
                'file_path': video_path,
                'filename': output_filename
            }
            
        except Exception as e:
            print(f"Error processing file: {e}")
            utils.download_progress[download_id] = {
                'status': 'error',
                'error': str(e)
            }
            
    except Exception as e:
        print(f"Download process error: {e}")
        utils.download_progress[download_id] = {
            'status': 'error',
            'error': str(e)
        }

@csrf_exempt
def get_download_file(request: HttpRequest) -> FileResponse:
    """Get the downloaded file"""
    if request.method == 'POST':
        download_id = request.POST.get('download_id')
        if download_id in utils.download_progress:
            progress = utils.download_progress[download_id]
            if progress['status'] == 'completed':
                response = FileResponse(
                    open(progress['file_path'], 'rb'),
                    as_attachment=True,
                    filename=progress['filename']
                )
                response['Content-Length'] = os.path.getsize(progress['file_path'])
                return response
    
    return JsonResponse({'error': 'File not found'}, status=404)
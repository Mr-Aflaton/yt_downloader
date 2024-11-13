import os
import subprocess
import traceback

from django.http import FileResponse, HttpRequest, HttpResponse
from django.shortcuts import render
from django.contrib import messages
import yt_dlp
from . import utils

DOWNLOAD_DIR = 'temp_downloads'

os.makedirs(DOWNLOAD_DIR, exist_ok=True)

def process_url(request: HttpRequest) -> HttpResponse:
    """
    Gets available formats from youtube link.
    
    Args:
        request (HttpRequest): Django request object
    
    Returns:
        HttpResponse: Rendered page with format options
    """
    context = {}
    
    if request.method == 'POST':
        url = request.POST.get('url')
        is_url_valid = utils.validate_youtube_url(url)
        if is_url_valid == True:
            video_details = utils.extract_video_info(url)
        else:
            video_details = None
        if not video_details or video_details['formats'] == []:
            if is_url_valid == True:
                messages.error(request, f"Can't find video. Check the provided YouTube link.")
            else:
                messages.error(request, f"Can't extract video information. {is_url_valid}")
            return render(request, 'downloader/index.html', context)
        context.update(video_details)
    return render(request, 'downloader/index.html', context)

def download_vid(request: HttpRequest) -> FileResponse:
    """
    Downloads video and returns it to the user.
    
    Args:
        request (HttpRequest): Django request object
    
    Returns:
        FileResponse: literally the file after it's downloaded, or a response if there's an error.
    """
    for file in os.listdir(DOWNLOAD_DIR):
        os.remove(os.path.join(DOWNLOAD_DIR, file))
    
    if request.method == 'POST':
        url = request.POST.get('url')
        format_id = request.POST.get('format_id')
        
        if not url or not format_id:
            messages.error(request, "Invalid download request")
            return render(request, 'downloader/index.html')
        
        video_format_id = format_id.split('+')[0]
        audio_format_id = None
        if '+' in format_id:
            audio_format_id = format_id.split('+')[1]
        
        video_filename, audio_filename = utils.download_video(url, video_format_id, DOWNLOAD_DIR, audio_format_id)
        
        if not video_filename or not os.path.exists(video_filename):
            messages.error(request, "Download failed")
            return render(request, 'downloader/index.html')
        
        try:
            output_filename = os.path.basename(video_filename)
            
            if audio_filename and os.path.exists(audio_filename):
                output_path = os.path.join(DOWNLOAD_DIR, f"Youtube Downloader - {output_filename}")
                print("Downloaded, now merging...")
                if utils.merge_video_audio(video_filename, audio_filename, output_path):
                    os.remove(video_filename)
                    os.remove(audio_filename)
                    video_filename = output_path
                    output_filename = os.path.basename(output_path)
            
            response = FileResponse(
                open(video_filename, 'rb'),
                as_attachment=True,
                filename=output_filename
            )
            
            response.close_on_exit = False
            
            return response
        
        except Exception as e:
            print(f"Error returning file: {video_filename}\n{traceback.format_exc()}")
            messages.error(request, "Error downloading file...")
            return render(request, 'downloader/index.html')


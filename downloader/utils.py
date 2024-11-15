import os
import subprocess
import traceback

from django.http import FileResponse
from django.shortcuts import render
from django.contrib import messages
import yt_dlp


def validate_youtube_url(url: str) -> str:
    """validates the url put by the user.

    Args:
        url (str): Youtube Link

    Returns:
        Bool or error string: 
    """
    try:
        if not url.startswith(('http://', 'https://')):
            return "Invalid URL format"
        if 'youtube.com' not in url and 'youtu.be' not in url:
            return "Not a valid YouTube url"
        return True
    except Exception as e:
        print(f"URL validation failed: \n{traceback.format_exc()}")
        return "Invalid url"

def extract_video_info(url: str) -> dict:
    """
    Gets video info.
    
    Args:
        url (str): YouTube video URL
    
    Returns:
        dict: Video information or None if it encoutered an error
    """
    try:
        ydl_opts = {
            'quiet': True,
            'no_warnings': True,
            'nooverwrites': True,
            'no_color': True,
        }
        
        with yt_dlp.YoutubeDL(ydl_opts) as ydl:
            info_dict = ydl.extract_info(url, download=False)
            
            video_details = {
                'title': info_dict.get('title', 'Unknown Title'),
                'thumbnail': info_dict.get('thumbnail', ''),
                'formats': [],
                'url': url
            }
            
            video_formats = []
            audio_formats = []
            video_dictionary = {}
            
            for format in info_dict.get('formats', []):
                if format.get('ext') in ['mp4', 'webm', 'm4a']:
                    format_info = {
                        'format_id': format.get('format_id', ''),
                        'resolution': format.get('resolution', 'Unknown'),
                        'ext': format.get('ext', ''),
                        'filesize': get_filesize(format.get('filesize', 0)),
                        'tbr': format.get('tbr', 0),
                        'vcodec': format.get('vcodec', 'None'),
                        'acodec': format.get('acodec', 'None'),
                    }
                    
                    if format_info['filesize'] == "Unknown":
                        continue
                    
                    if format_info['vcodec'] != 'none' and format_info['acodec'] == 'none':
                        video_formats.append(format_info)
                    elif format_info['acodec'] != 'none' and format_info['vcodec'] == 'none':
                        audio_formats.append(format_info)
            
            video_formats = [i for i in video_formats if i['ext'] == 'mp4']
            actual_videos = []
            for video in video_formats:
                video_dictionary[video['resolution'] + "-" + video['filesize']] = 1
            
            for v in video_dictionary.keys():
                temp_videos = []
                for video in video_formats:
                    if video['resolution'] == v.split('-')[0] and video['filesize'] == v.split('-')[1]:
                        temp_videos.append(video)
                actual_videos.append(temp_videos[-1])
            
            audio_dictionary = {}
            actual_audios = []
            for audio in audio_formats:
                audio_dictionary[audio['ext']] = 1
            for v in audio_dictionary.keys():
                temp_audios = []
                for audio in audio_formats:
                    if audio['ext'] == v.split('-')[0]:
                        temp_audios.append(audio)
                actual_audios.append(temp_audios[-1])
            
            video_formats = actual_videos
            audio_formats = actual_audios
            for video in video_formats:
                for audio in audio_formats[-1:]:
                    combined_format = video.copy()
                    combined_format['format_id'] = f"{video['format_id']}+{audio['format_id']}"
                    combined_format['audio_format_id'] = audio['format_id']
                    combined_format['type'] = 'video'
                    video_details['formats'].append(combined_format)
            for audio in audio_formats[:]:
                combined_format = audio.copy()
                combined_format['format_id'] = f"{audio['format_id']}"
                combined_format['audio_format_id'] = audio['format_id']
                combined_format['type'] = 'audio'
                video_details['formats'].append(combined_format)
            return video_details
    
    except Exception as e:
        print(f"Error while extracting video info: {traceback.format_exc()}")
        return None

def download_video(url: str, format_id: str, download_dir: str, audio_format_id: str = None) -> tuple:
    """
    Download video after use selects format and resolution
    
    Args:
        url (str): YouTube video link
        format_id (str): format id (from the extracted info)

    Returns:
        tuple: Path to downloaded video and audio files (or None)
    """
    
    try:
        ydl_opts = {
            'quiet': True,
            'no_warnings': True,
            'format': format_id,
            'outtmpl': os.path.join(download_dir, '%(title)s_video.%(ext)s'),
        }
        
        with yt_dlp.YoutubeDL(ydl_opts) as ydl:
            info_dict = ydl.extract_info(url, download=True)
            video_filename = ydl.prepare_filename(info_dict)
        
        audio_filename = None
        
        if audio_format_id:
            ydl_opts['format'] = audio_format_id
            ydl_opts['outtmpl'] = os.path.join(download_dir, '%(title)s_audio.%(ext)s')
            
            with yt_dlp.YoutubeDL(ydl_opts) as ydl:
                info_dict = ydl.extract_info(url, download=True)
                audio_filename = ydl.prepare_filename(info_dict)
        
        return video_filename, audio_filename
    
    except Exception as e:
        print(f"Download error: {traceback.format_exc()}")
        return None, None

def get_filesize(size: float) -> float:
    """
    Make file size easy to read
    
    Args:
        size (int): File size in bytes
    
    Returns:
        str: Formatted file size
    """
    if size == 0 or not size or size == None:
        return "Unknown"
    
    for unit in ['B', 'KB', 'MB', 'GB']:
        if size < 1024.0:
            return f"{size:.2f} {unit}"
        size /= 1024.0

def merge_video_audio(video_path: str, audio_path: str, output_path: str) -> bool:
    """
    merge video and audio using ffmpeg
    
    Args:
        video_path (str): video path
        audio_path (str): audio path
        output_path (str): output path
    
    Returns:
        bool: is it merged successfully?
    """
    try:
        ffmpeg_command = [
            'ffmpeg',
            '-i', video_path,
            '-i', audio_path,
            '-c:v', 'copy',
            '-c:a', 'aac',
            # '-strict', 'experimental',
            '-preset', 'ultrafast',
            '-threads', '4',
            '-y',
            output_path
        ]
        result = subprocess.run(ffmpeg_command, text=True)
        if result.returncode == 0:
            return True
        else:
            print(f"FFmpeg error: {result.stderr}")
            return False
    
    except Exception as e:
        print(f"Merge error: {traceback.format_exc()}")
        return False

import os
import subprocess
import traceback

from django.http import FileResponse
from django.shortcuts import render
from django.contrib import messages
import yt_dlp
import json
import ffmpeg

download_progress = {}

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
    """
    try:
        download_id = f"{url}_{format_id}+{audio_format_id}"

        def progress_hook(d):
            if d['status'] == 'downloading':
                try:
                    total = d.get('total_bytes', 0) or d.get('total_bytes_estimate', 0)
                    downloaded = d.get('downloaded_bytes', 0)
                    if total > 0:
                        
                        
                        base_percentage = 45 if audio_format_id else 100
                        percentage = (downloaded / total) * base_percentage
                        
                        
                        stage = download_progress[download_id].get('stage', 'video')
                        if stage == 'audio':
                            percentage += 45  
                        
                        download_progress[download_id].update({
                            'status': 'downloading',
                            'progress': percentage,
                            'speed': d.get('speed', 0),
                            'eta': d.get('eta', 0),
                            'stage': stage
                        })
                except:
                    pass
            elif d['status'] == 'finished':
                stage = download_progress[download_id].get('stage', 'video')
                if stage == 'video' and audio_format_id:
                    
                    download_progress[download_id].update({
                        'status': 'downloading',
                        'progress': 45,
                        'stage': 'audio'
                    })
                elif stage == 'audio':
                    
                    download_progress[download_id].update({
                        'status': 'downloading',
                        'progress': 90,
                        'stage': 'merging'
                    })
                else:
                    
                    download_progress[download_id].update({
                        'status': 'finished',
                        'progress': 100,
                        'stage': 'complete'
                    })

        ydl_opts = {
            'quiet': True,
            'no_warnings': True,
            'format': format_id,
            'outtmpl': os.path.join(download_dir, '%(title)s_video.%(ext)s'),
            'progress_hooks': [progress_hook],
        }
        
        
        download_progress[download_id] = {
            'status': 'downloading',
            'progress': 0,
            'stage': 'video',
            'speed': 0,
            'eta': 0
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
        download_progress[download_id] = {
            'status': 'error',
            'error': str(e)
        }
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


def merge_video_audio(video_path: str, audio_path: str, output_path: str, download_id: str) -> bool:
    """
    Merge video and audio using ffmpeg-python
    """
    try:
        
        if download_id in download_progress:
            download_progress[download_id].update({
                'status': 'downloading',
                'progress': 90,
                'stage': 'merging'
            })

        video = ffmpeg.input(video_path)
        audio = ffmpeg.input(audio_path)
        print(video_path, audio_path)
        stream = ffmpeg.output(
            video,
            audio,
            output_path,
            vcodec='copy',
            acodec='aac',
            preset='ultrafast',
            threads=4,
            loglevel='quiet'
        )
        try:
            ffmpeg.run(stream, overwrite_output=True, capture_stderr=True)
        except Exception as e:
            print(e)
            print(traceback.format_exc())
        
        if download_id in download_progress:
            download_progress[download_id].update({
                'status': 'finished',
                'progress': 100,
                'stage': 'complete'
            })

        return True
    
    except Exception as e:
        print(e)
        print(f"Merge error: {traceback.format_exc()}")
        if download_id in download_progress:
            download_progress[download_id].update({
                'status': 'error',
                'error': 'Merging failed: ' + str(e)
            })
        return False

def extract_playlist_info(url: str) -> dict:
    """
    Extracts information about all videos in a playlist
    
    Args:
        url (str): YouTube playlist URL
    
    Returns:
        dict: Playlist information or None if error
    """
    try:
        ydl_opts = {
            'quiet': True,
            
            'extract_flat': True,
        }
        
        with yt_dlp.YoutubeDL(ydl_opts) as ydl:
            info_dict = ydl.extract_info(url, download=False)
            
            if 'entries' not in info_dict:
                info_dict = ydl.extract_info(info_dict['url'], download=False)
                print(json.dumps(info_dict, indent=4 ))                
                
                if 'entries' not in info_dict:
                    return None
                
                
            playlist_details = {
                'title': info_dict.get('title', 'Unknown Playlist'),
                'videos': []
            }
            
            for idx, entry in enumerate(info_dict['entries'], 1):
                video_info = {
                    'title': entry.get('title', 'Unknown Title'),
                    'url': f"https://www.youtube.com/watch?v={entry['id']}",
                    'thumbnail': entry.get('thumbnail', ''),
                    'position': idx
                }
                playlist_details['videos'].append(video_info)
                
            return playlist_details
    
    except Exception as e:
        print(f"Error extracting playlist info: {traceback.format_exc()}")
        return None

def is_playlist_url(url: str) -> bool:
    """
    Check if URL is a playlist
    
    Args:
        url (str): YouTube URL
    
    Returns:
        bool: True if playlist URL
    """
    return 'playlist' in url or '&list=' in url
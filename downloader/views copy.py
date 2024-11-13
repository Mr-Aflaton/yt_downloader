import os
from django.http import FileResponse, Http404
from django.shortcuts import render
from django.contrib import messages
import yt_dlp

class VideoDownloaderView:
    def __init__(self):
        # Temporary download directory
        self.download_dir = 'temp_downloads'
        os.makedirs(self.download_dir, exist_ok=True)

    def extract_video_info(self, url):
        """
        Extract video information using yt-dlp
        
        Args:
            url (str): YouTube video URL
        
        Returns:
            dict: Video information or None
        """
        try:
            ydl_opts = {
                'quiet': True,
                'no_warnings': True,
                'nooverwrites': True,
                'no_color': True,
            }
            
            with yt_dlp.YoutubeDL(ydl_opts) as ydl:
                # Extract video information
                info_dict = ydl.extract_info(url, download=False)
                
                # Prepare video details
                video_details = {
                    'title': info_dict.get('title', 'Unknown Title'),
                    'thumbnail': info_dict.get('thumbnail', ''),
                    'formats': [],
                    'url': url
                }
                
                # Process available formats
                print([i['ext'] for i in info_dict['formats']])
                for format in info_dict.get('formats', []):
                    # Filter for relevant formats
                    if format.get('ext') in ['mp4', 'webm', 'm4a', 'mp3']:
                        format_info = {
                            'format_id': format.get('format_id', ''),
                            'resolution': format.get('resolution', 'Unknown'),
                            'ext': format.get('ext', ''),
                            'filesize': self._format_filesize(format.get('filesize', 0)),
                            'tbr': format.get('tbr', 0),
                            'vcodec': format.get('vcodec', 'None'),
                            'acodec': format.get('acodec', 'None'),
                        }
                        
                        if format_info['filesize'] == "Unknown":
                            continue
                        # print(format_info['filesize'])
                        
                        # Categorize formats
                        print(format_info['vcodec'], format_info['acodec'])
                        if format_info['vcodec'] != 'none' and format_info['acodec'] != 'none':
                            format_info['type'] = 'video'
                        elif format_info['acodec'] != 'none':
                            format_info['type'] = 'audio'
                        else:
                            format_info['type'] = 'unknown'
                        
                        video_details['formats'].append(format_info)
                
                return video_details
        
        except Exception as e:
            print(f"Error extracting video info: {e}")
            return None

    def download_video(self, url, format_id):
        """
        Download video with specified format
        
        Args:
            url (str): YouTube video URL
            format_id (str): Format identifier
        
        Returns:
            str: Path to downloaded file or None
        """
        try:
            # Download options
            ydl_opts = {
                'quiet': True,
                'no_warnings': True,
                'format': format_id,
                'outtmpl': os.path.join(self.download_dir, '%(title)s.%(ext)s'),
            }
            
            # Download video
            with yt_dlp.YoutubeDL(ydl_opts) as ydl:
                info_dict = ydl.extract_info(url, download=True)
                
                # Get the downloaded file path
                filename = ydl.prepare_filename(info_dict)
                
                return filename
        
        except Exception as e:
            print(f"Download error: {e}")
            return None

    def _format_filesize(self, size):
        """
        Convert file size to human-readable format
        
        Args:
            size (int): File size in bytes
        
        Returns:
            str: Formatted file size
        """
        if size == 0:
            return "Unknown"
        
        for unit in ['B', 'KB', 'MB', 'GB']:
            if size < 1024.0:
                return f"{size:.2f} {unit}"
            size /= 1024.0
        
        return f"{size:.2f} TB"

    def download_view(self, request):
        """
        Handle video download request
        
        Args:
            request (HttpRequest): Django request object
        
        Returns:
            FileResponse or render
        """
        if request.method == 'POST':
            url = request.POST.get('url')
            format_id = request.POST.get('format_id')
            
            # Validate inputs
            if not url or not format_id:
                messages.error(request, "Invalid download request")
                return render(request, 'downloader/index.html')
            
            # Download video
            downloaded_file_path = self.download_video(url, format_id)
            
            if not downloaded_file_path or not os.path.exists(downloaded_file_path):
                messages.error(request, "Download failed")
                return render(request, 'downloader/index.html')
            
            try:
                # Prepare file for download
                response = FileResponse(
                    open(downloaded_file_path, 'rb'),
                    as_attachment=True,
                    filename=os.path.basename(downloaded_file_path)
                )
                
                # Clean up the temporary file after sending
                def cleanup(response):
                    os.remove(downloaded_file_path)
                    return response
                
                response.close_on_exit = False
                
                # Delete the file after download
                try:
                    # import os
                    os.remove(downloaded_file_path)
                except Exception as e:
                    print(f"Error deleting file: {e}")
                
                return response
            
            except Exception as e:
                print(f"Error serving file: {e}")
                messages.error(request, "Error serving downloaded file")
                return render(request, 'downloader/index.html')

    def process_url(self, request):
        """
        Process YouTube URL and return available formats
        
        Args:
            request (HttpRequest): Django request object
        
        Returns:
            HttpResponse: Rendered page with format options
        """
        context = {}
        
        if request.method == 'POST':
            url = request.POST.get('url')
            
            # Validate URL and extract info
            video_details = self.extract_video_info(url)
            
            if not video_details:
                messages.error(request, "Invalid YouTube URL or unable to extract information")
                return render(request, 'downloader/index.html', context)
            
            context.update(video_details)
        
        return render(request, 'downloader/index.html', context)

# Usage in urls.py
# from django.urls import path
# view = VideoDownloaderView()
# urlpatterns = [
#     path('', view.process_url, name='index'),
#     path('download/', view.download_view, name='download'),
# ]
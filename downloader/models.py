# models.py
from django.db import models

class VideoHistory(models.Model):
    title = models.CharField(max_length=255)
    url = models.URLField()
    thumbnail = models.URLField()
    lookup_date = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ['-lookup_date']

    def __str__(self):
        return self.title

class PlaylistVideo(models.Model):
    playlist_id = models.CharField(max_length=100)
    title = models.CharField(max_length=255)
    url = models.URLField()
    thumbnail = models.URLField()
    position = models.IntegerField()

    class Meta:
        ordering = ['position']

    def __str__(self):
        return f"{self.position}. {self.title}"
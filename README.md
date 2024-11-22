# Youtube Downloader

A simple Django-based Python web app to download Youtube Videos.

This project is meant for developers now, since it's a small part of a bigger project, but intend to make this as a standalone project that's fully functional and could be deployed anywhere.

# Instructions for running the server

Clone the repo:
```bash
git clone https://github.com/Mr-Aflaton/yt_downloader
```

Install requirements:
```bash
cd yt_downloader
pip install -r requirements.txt
```

Install FFMPEG on the server:
```bash
sudo apt install ffmpeg
```

Run the server:
```bash
python manage.py runserver
```

# notes

All of the heavy work is in utils.py, views.py is just for handling http requests and responses.


# Future plans

- [ ] Download playlists (dynamically select resolutions)
- [ ] Caching already downloaded videos and storing them in the database.
- [ ] Dockerize the project.


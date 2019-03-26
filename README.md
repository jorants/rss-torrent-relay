# rss-torrent-relay
This application reads in a rss feed of torrents and parses the titles.
It figures out which torrents co respond to unseen episodes of TV shows and saves these. 
It then builds a new rss feed of only those those torrents that could be added to your torrent client.

Set everything in config.py and run wsgi.py either directly for testing or through uwsgi. The database is automaticly created.
Make sure the server has write access to its own directory, it needs to store the torrent files on disk.

import os

basedir = os.path.abspath(os.path.dirname(__file__))


class Config(object):
    SQLALCHEMY_DATABASE_URI = os.environ.get(
        "DATABASE_URL"
    ) or "sqlite:///" + os.path.join(basedir, "app.db")
    SQLALCHEMY_TRACK_MODIFICATIONS = False

    # list of regexes that parses a torrent name
    # tags should be a space seperated list of tags at the moment.
    PARSE_RE = [
        r"^(?P<show>.*) s(?P<season>[0-9][0-9])e(?P<episode>[0-9][0-9])(?P<tags>[\w\- ]*)-.*$"
    ]

    # Shows you want
    SHOWS = ["arrow", "the flash 2014", "supergirl"]

    # These Tags should be present for downloading a torrent
    TAGS = set(["x264", "h264"])

    # The feed you want to relay
    FEED = "RSS_FEED_URL"

    # Your feed will be add /feed/<URL_KEY>/
    URL_KEY = "SECRET_STRING"

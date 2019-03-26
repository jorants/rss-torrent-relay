#!/usr/bin/python3
import sys, os, re, datetime

from flask import Flask, request, abort, send_from_directory, url_for
from flask_sqlalchemy import SQLAlchemy
from werkzeug.contrib.atom import AtomFeed
import atexit
from apscheduler.schedulers.background import BackgroundScheduler
from sqlalchemy.exc import OperationalError

import feedparser
import requests
import hashlib

from config import Config

app = Flask(__name__)
app.config.from_object(Config)
db = SQLAlchemy(app)


class Episode(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    title = db.Column(db.String(512))
    show = db.Column(db.String(512))
    season = db.Column(db.Integer)
    episode = db.Column(db.Integer)
    torrentlink = db.Column(db.String(512))
    added = db.Column(db.DateTime, default=datetime.datetime.now())

    def __repr__(self):
        return "<%s %i:%i>" % (self.show, self.season, self.episode)

    def sort_key(self):
        return sort_key(self.season, self.episode)


# Test if the database already exists, if not, make it
try:
    Episode.query.count()
except OperationalError:
    db.create_all()


def parse_title(title):
    title = title.lower()

    # test all possible formats until a fitting one is found or return None
    for exp in app.config["PARSE_RE"]:
        parts = re.search(exp, title)

        if parts != None:
            parsed = parts.groupdict()
            parsed["show"] = parsed["show"].strip()
            parsed["tags"] = parsed["tags"].strip().split()
            try:
                parsed["season"] = int(parsed["season"])
                parsed["episode"] = int(parsed["episode"])
            except ValueError:
                return

            return parsed


def update_feed():
    # This parses the feed and looks for any hits
    org_feed = feedparser.parse(app.config["FEED"])
    for entry in reversed(org_feed.entries):
        link = entry["link"]
        title = entry["title"]
        date = entry.published

        episode = parse_title(title)

        if episode == None:
            # No fitting format was found
            continue

        # Check if we want this show, the tags match, and the episode is the newest
        if (
            episode["show"] in app.config["SHOWS"]
            and set(episode["tags"]).intersection(app.config["TAGS"])
            and Episode.query.filter(
                episode.show == episode["show"],
                Episode.season >= episode["season"],
                Episode.episode >= episode["episode"],
            ).count()
            == 0
        ):
            # New episode, whoooooo :-) add it.
            epp = Episode(
                title=title,
                show=episode["show"],
                season=episode["season"],
                episode=episode["episode"],
                torrentlink=link,
            )

            db.session.add(epp)
            db.session.commit()
            print(epp)


# Even though we update the feed every time we get checked, we also want to check on our own from time to time so we do not miss anything:
scheduler = BackgroundScheduler()
scheduler.add_job(func=update_feed, trigger="interval", minutes=30)
scheduler.start()
atexit.register(lambda: scheduler.shutdown())


@app.route("/feed/" + app.config["URL_KEY"])
def feed():
    update_feed()
    toshow = Episode.query.order_by(Episode.added.desc()).limit(20)
    feed = AtomFeed(title="My Torrents", feed_url=request.url, url=request.url_root)
    for epp in toshow:
        feed.add(
            epp.title,
            "%s S%02iE%02i" % (epp.show, epp.season, epp.episode),
            link="/" + str(epp.id) + ".torrent",
            url="/" + str(epp.id) + ".torrent",
            published=epp.added,
            updated=epp.added,
            id=epp.id,
        )

    return feed.get_response()


@app.route("/feed/" + app.config["URL_KEY"] + "/<int:idd>.torrent")
def torrent(idd):
    # Download a torrent if needed, and serve it back.

    epp = Episode.query.filter(Episode.id == idd).first()
    if epp == None:
        abort(404)

    url = epp.torrentlink
    fn = hashlib.sha224(url.encode()).hexdigest() + ".torrent"

    # ensure the folder exists
    if not os.path.exists("torrents"):
        os.makedirs("torrents")

    path = "torrents/" + fn
    # Download if not already done
    if not os.path.exists(path):
        r = requests.get(url)
        with open(path, "wb") as f:
            f.write(r.content)

    return send_from_directory("torrents", fn)


@app.route("/")
def index():
    return "Not here :-O"

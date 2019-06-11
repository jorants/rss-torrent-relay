#!/usr/bin/python3
import sys, os, re, datetime

from flask import Flask, request, abort, send_from_directory, url_for
from werkzeug.contrib.atom import AtomFeed
import atexit
from apscheduler.schedulers.background import BackgroundScheduler

import feedparser
import requests
import hashlib
import fnmatch

from config import Config
import peewee
from playhouse.db_url import connect

import flask_admin
from flask_admin.contrib.peewee import ModelView


app = Flask(__name__)
app.config.from_object(Config)


db = connect(app.config["DATABASE_URI"])


class BaseModel(peewee.Model):
    class Meta:
        database = db


class Show(BaseModel):
    name = peewee.CharField(512)
    last_season = peewee.IntegerField()
    last_episode = peewee.IntegerField()


class Episode(BaseModel):
    title = peewee.CharField(512)
    show = peewee.ForeignKeyField(Show, backref="episodes")
    season = peewee.IntegerField()
    episode = peewee.IntegerField()
    torrentlink = peewee.CharField(512)
    added = peewee.DateTimeField(default=datetime.datetime.now)

    def __repr__(self):
        return "<%s %i:%i>" % (self.show, self.season, self.episode)


db_classes = BaseModel.__subclasses__()
db.create_tables(db_classes)


admin = flask_admin.Admin(app, name='microblog', template_mode='bootstrap3',url="/admin/"+app.config["URL_KEY"])
admin.add_view(ModelView(Show))
admin.add_view(ModelView(Episode))


PARSE_RE = r"^(?P<show>.*) s(?P<season>[0-9][0-9])e(?P<episode>[0-9][0-9])(?P<tags>[\w ]*)-(?P<uploader>.*)$"


def parse_title(title):

    title = title.lower().replace(".", " ")
    parts = re.search(PARSE_RE, title)

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

def match_tags(formats, tags):

    for f in formats:
        if len(fnmatch.filter(tags, f)) > 0:
            return True
    return False


def update_feed():
    org_feed = feedparser.parse(app.config["FEED"])
    for entry in reversed(org_feed.entries):
        link = entry["link"]
        title = entry["title"]
        date = entry.published
        episodeinfo = parse_title(title)
        if episodeinfo == None:
            continue


        if Show.select().where(Show.name == episodeinfo["show"]).count() > 0 and match_tags(app.config["TAGS"],episodeinfo["tags"]):

            show = Show.get(Show.name == episodeinfo["show"])
            if (show.last_season, show.last_episode) < (episodeinfo["season"],episodeinfo["episode"]):
                show.last_season = episodeinfo["season"]
                show.last_episode = episodeinfo["episode"]
                show.save()

                epp = Episode(
                    title=title,
                    show=show,
                    season=episodeinfo["season"],
                    episode=episodeinfo["episode"],
                    torrentlink=link,
                )
                print(epp)
                epp.save()


scheduler = BackgroundScheduler()
scheduler.add_job(func=update_feed, trigger="interval", minutes=30)
scheduler.start()
atexit.register(lambda: scheduler.shutdown())


@app.route("/feed/" + app.config["URL_KEY"])
def feed():
    update_feed()
    toshow = Episode.select().order_by(Episode.added.desc()).limit(20)
    feed = AtomFeed(title="My Torrents", feed_url=request.url, url=request.url_root)
    for epp in toshow:
        feed.add(
            epp.title,
            "%s S%02iE%02i" % (epp.show.name, epp.season, epp.episode),
            link="/" + str(epp.id) + ".torrent",
            url="/" + str(epp.id) + ".torrent",
            published=epp.added,
            updated=epp.added,
            id=epp.id,
        )

    return feed.get_response()


@app.route("/feed/" + app.config["URL_KEY"] + "/<int:idd>.torrent")
def torrent(idd):
    try:
        epp = Episode.get_by_id(idd)
    except DoesNotExist:
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
    return "Not here"


if __name__ == "__main__":
    update_feed()
    app.run()

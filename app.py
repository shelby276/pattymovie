import os
import time

import requests
from flask import Flask, render_template, request, abort

app = Flask(__name__)

API_KEY = os.environ.get("TMDB_API_KEY", "")
BASE = "https://api.themoviedb.org/3"
IMG = "https://image.tmdb.org/t/p"
_cache = {}


def tmdb(path, **params):
    key = (path, tuple(sorted(params.items())))
    hit = _cache.get(key)
    if hit and time.time() - hit[0] < 600:
        return hit[1]
    params.update(api_key=API_KEY, language="fr-FR")
    try:
        r = requests.get(BASE + path, params=params, timeout=10)
        r.raise_for_status()
        data = r.json()
    except requests.RequestException:
        return {}
    _cache[key] = (time.time(), data)
    return data


def items(path, media_type=None, **params):
    out = []
    for i in tmdb(path, **params).get("results", []):
        i["media_type"] = media_type or i.get("media_type")
        if i["media_type"] in ("movie", "tv") and i.get("poster_path"):
            out.append(i)
    return out


@app.context_processor
def helpers():
    return {"img": lambda p, size="w342": f"{IMG}/{size}{p}" if p else ""}


@app.route("/")
def home():
    trending = items("/trending/all/week")
    hero = next((i for i in trending if i.get("backdrop_path")), None)
    rows = [
        ("Tendances de la semaine", trending),
        ("Films populaires", items("/movie/popular", "movie")),
        ("Séries populaires", items("/tv/popular", "tv")),
        ("Films les mieux notés", items("/movie/top_rated", "movie")),
        ("Séries les mieux notées", items("/tv/top_rated", "tv")),
    ]
    return render_template("index.html", hero=hero, rows=rows, query=None)


@app.route("/recherche")
def search():
    q = request.args.get("q", "").strip()
    results = items("/search/multi", query=q) if q else []
    return render_template("index.html", hero=None, rows=[], results=results, query=q)


@app.route("/<media_type>/<int:tmdb_id>")
def detail(media_type, tmdb_id):
    if media_type not in ("movie", "tv"):
        abort(404)
    d = tmdb(
        f"/{media_type}/{tmdb_id}",
        append_to_response="videos,credits,similar",
        include_video_language="fr,en,null",
    )
    if not d:
        abort(404)
    videos = d.get("videos", {}).get("results", [])
    trailer = next(
        (v for v in videos if v["site"] == "YouTube" and v["type"] == "Trailer"), None
    ) or next((v for v in videos if v["site"] == "YouTube"), None)
    similar = [
        dict(s, media_type=media_type)
        for s in d.get("similar", {}).get("results", [])
        if s.get("poster_path")
    ]
    return render_template(
        "detail.html", d=d, media_type=media_type, trailer=trailer,
        cast=d.get("credits", {}).get("cast", [])[:8], similar=similar,
    )


if __name__ == "__main__":
    app.run(debug=True)

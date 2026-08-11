import json
import os
import re
import urllib.parse
import urllib.request

from flask import current_app

ENDPOINT = "https://en.wikipedia.org/w/api.php"

USER_AGENT = "IMSE-Group05-BoatRental/1.0 (university project; contact via repo)"

TIMEOUT_SECONDS = 3

CITY_ARTICLES = {
    "Santorini": "Fira",
    "Mykonos": "Church of Panagia Paraportiani",
}

# The boats are generated -- "Manufacturer4" is not a real builder, so there is
# nothing to photograph per hull. One representative image per type is the
# honest granularity. These three articles were picked because their lead image
# is actually a charter-style vessel.
BOAT_TYPE_ARTICLES = {
    "yacht": "Yacht",
    "catamaran": "Lagoon 380",
    "motorboat": "Princess Yachts",
}


# A place article's lead image is very often a flag, a locator map or a coat of
# arms rather than a photograph -- "Mallorca" resolves to Flag_of_Mallorca.svg.
# Those are worse than nothing here, so they are dropped and the card falls back
# to its tinted panel. Matched with separators so a real photo whose caption
# happens to contain one of these words is not thrown away.
_NOT_A_PHOTO = re.compile(
    r"(^|[_\-.%28 ])("
    r"flag|flags|map|maps|locator|location|borders|outline|topographic|"
    r"coat[_\- ]of[_\- ]arms|blason|escudo|seal|logo|emblem|nomos|dimos|"
    r"banner|arms"
    r")([_\-.%29 ]|$)",
    re.IGNORECASE,
)


def _looks_like_a_photo(url):
    name = url.rsplit("/", 1)[-1].split("?", 1)[0]
    # A raster rendered from an SVG is a diagram by definition.
    if ".svg." in name.lower():
        return False
    return not _NOT_A_PHOTO.search(name)


# The rotating hero pool. Mediterranean anchorages rather than generic "yacht"
# stock: this is the coastline the fleet actually works, and every one of these
# articles leads with a wide landscape photograph.
HERO_ARTICLES = [
    "Portofino", "Amalfi Coast", "Bay of Kotor", "Saint-Tropez", "Hvar",
    "Cinque Terre", "Positano", "Bonifacio, Corse-du-Sud", "Porto Cervo",
    "Costa Brava", "Cassis", "Split, Croatia",
]

# Anything squarer than this gets cropped to a letterbox sliver in the hero.
HERO_MIN_ASPECT = 1.3


def _enabled():
    return os.environ.get("IMAGE_FETCH", "on").lower() not in ("off", "0", "false")


def _fetch(titles, width, min_aspect=0):
    """title -> thumbnail URL for whatever the API could resolve.

    min_aspect drops portrait images. The API hands back the thumbnail's real
    dimensions, so this is free -- and it matters for the hero, where a tall
    photo gets cropped to a sliver of itself.
    """
    query = urllib.parse.urlencode({
        "action": "query",
        "format": "json",
        "prop": "pageimages",
        "piprop": "thumbnail",
        "pithumbsize": width,
        "pilicense": "free",
        "redirects": 1,
        "titles": "|".join(titles),
    })
    request = urllib.request.Request(
        f"{ENDPOINT}?{query}", headers={"User-Agent": USER_AGENT}
    )
    with urllib.request.urlopen(request, timeout=TIMEOUT_SECONDS) as response:
        payload = json.load(response)

    found = {}
    for page in payload.get("query", {}).get("pages", {}).values():
        thumb = page.get("thumbnail") or {}
        source, w, h = thumb.get("source"), thumb.get("width", 0), thumb.get("height", 1)
        if not source or not _looks_like_a_photo(source):
            continue
        if min_aspect and (w / h if h else 0) < min_aspect:
            continue
        found[page["title"]] = source

    for redirect in payload.get("query", {}).get("redirects", []):
        if redirect["to"] in found:
            found[redirect["from"]] = found[redirect["to"]]

    return found


def lookup(article_by_key, width=640, min_aspect=0):
    """key -> image URL, for the keys that resolved. Never raises."""
    if not article_by_key or not _enabled():
        return {}

    try:
        articles = list(dict.fromkeys(article_by_key.values()))[:50]
        by_title = _fetch(articles, width, min_aspect)
    except Exception:
        current_app.logger.warning("Image lookup failed; falling back to placeholders",
                                   exc_info=True)
        return {}

    return {
        key: by_title[article]
        for key, article in article_by_key.items()
        if article in by_title
    }


def hero_slides(limit=6, width=960):
    """[(url, place)] for the rotating hero. One request; [] on any failure.

    960px rather than 1280: these are background frames behind a scrim at 50%
    opacity, and the larger size cost roughly twice the bytes for a difference
    nobody can see through it. The template loads them one at a time, so the
    limit bounds total transfer, not first paint.
    """
    resolved = lookup(
        {name: name for name in HERO_ARTICLES},
        width=width,
        min_aspect=HERO_MIN_ASPECT,
    )
    return [
        (resolved[name], name.split(",")[0])
        for name in HERO_ARTICLES
        if name in resolved
    ][:limit]


def city_and_boat_images(cities, width=640):
    """One request covering both the harbour cards and the boat-type plates.

    Returns (city_url_by_city, image_url_by_boat_type).
    """
    city_articles = {c: CITY_ARTICLES.get(c, c) for c in cities}
    combined = dict(city_articles)
    combined.update({f"__type__{k}": v for k, v in BOAT_TYPE_ARTICLES.items()})

    resolved = lookup(combined, width)

    return (
        {c: resolved[c] for c in city_articles if c in resolved},
        {
            key: resolved[f"__type__{key}"]
            for key in BOAT_TYPE_ARTICLES
            if f"__type__{key}" in resolved
        },
    )

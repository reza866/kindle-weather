#!/usr/bin/env python3
"""Render a weather dashboard for a Kindle as site/weather.png + site/index.html.

Everything is drawn above `safe_height` so a damaged lower screen stays blank.
Data: Open-Meteo (no API key). Usage: python render.py [--sample]
Runs in GitHub Actions (see .github/workflows/update.yml); needs Pillow 13 / Python 3.11+.
"""
import json
import os
import sys
import time
import urllib.parse
import urllib.request
from datetime import datetime, timedelta, timezone

from PIL import Image, ImageDraw, ImageFont

ROOT = os.path.dirname(os.path.abspath(__file__))
S = 2  # supersampling factor: draw at 2x, shrink for smooth edges
BLACK, WHITE, GREY = 0, 255, 110

FONTS = {
    "bold": [
        "/usr/share/fonts/truetype/dejavu/DejaVuSans-Bold.ttf",
        "/System/Library/Fonts/Supplemental/Arial Bold.ttf",
    ],
    "regular": [
        "/usr/share/fonts/truetype/dejavu/DejaVuSans.ttf",
        "/System/Library/Fonts/Supplemental/Arial.ttf",
    ],
}


def font(kind, size):
    for path in FONTS[kind]:
        if os.path.exists(path):
            return ImageFont.truetype(path, int(size * S))
    raise SystemExit("No usable font found; install DejaVu Sans.")


# ---------- data ----------

def fetch(cfg):
    params = {
        "latitude": cfg["latitude"],
        "longitude": cfg["longitude"],
        "current": "temperature_2m,apparent_temperature,weather_code,wind_speed_10m",
        "daily": "weather_code,temperature_2m_max,temperature_2m_min,"
                 "precipitation_probability_max",
        "timezone": "auto",
        "forecast_days": 11,  # today + next 10 days
        "temperature_unit": cfg["temperature_unit"],
    }
    url = "https://api.open-meteo.com/v1/forecast?" + urllib.parse.urlencode(params)
    last = None
    for attempt in range(3):
        try:
            with urllib.request.urlopen(url, timeout=30) as r:
                return json.load(r)
        except Exception as e:  # network hiccup: retry
            last = e
            time.sleep(5 * (attempt + 1))
    raise SystemExit("Could not fetch forecast: %s" % last)


def sample():
    """Fixed data for offline layout checks."""
    now = datetime.now().replace(minute=0, second=0, microsecond=0)
    days = [now.date() + timedelta(days=i) for i in range(11)]
    return {
        "utc_offset_seconds": 0,
        "current": {"time": now.strftime("%Y-%m-%dT%H:%M"), "temperature_2m": -3.4,
                    "apparent_temperature": -7.1, "weather_code": 2,
                    "wind_speed_10m": 14.2},
        "current_units": {"wind_speed_10m": "km/h"},
        "daily": {"time": [d.isoformat() for d in days],
                  "weather_code": [2, 61, 3, 71, 95, 0, 45, 1, 80, 85, 3],
                  "temperature_2m_max": [1.3, 2.8, 0.1, -1.2, 4.0, -3.5, 0.0, 2.2, 3.1, -0.4, 1.0],
                  "temperature_2m_min": [-4.1, -2.2, -5.5, -9.0, 0.3, -12.0, -3.3, -2.0, -1.1, -6.6, -3.0],
                  "precipitation_probability_max": [20, 80, 40, 90, 60, 0, 10, 5, 70, 85, 30]},
    }


def describe(code):
    """WMO weather code -> (label, icon kind)."""
    if code == 0:
        return "Clear", "sun"
    if code == 1:
        return "Mostly clear", "sun"
    if code == 2:
        return "Partly cloudy", "partly"
    if code == 3:
        return "Overcast", "cloud"
    if code in (45, 48):
        return "Fog", "fog"
    if 51 <= code <= 57:
        return "Drizzle", "rain"
    if 61 <= code <= 67:
        return "Rain", "rain"
    if 71 <= code <= 77:
        return "Snow", "snow"
    if 80 <= code <= 82:
        return "Showers", "rain"
    if code in (85, 86):
        return "Snow showers", "snow"
    if code >= 95:
        return "Thunderstorm", "thunder"
    return "Unknown", "cloud"


# ---------- icons (drawn in a square of side s at x, y; already in 2x pixels) ----------

def _sun(d, cx, cy, r, st):
    import math
    for i in range(8):
        a = math.pi * i / 4
        d.line([cx + math.cos(a) * r * 1.35, cy + math.sin(a) * r * 1.35,
                cx + math.cos(a) * r * 1.85, cy + math.sin(a) * r * 1.85],
               fill=BLACK, width=int(st))
    d.ellipse([cx - r, cy - r, cx + r, cy + r], fill=BLACK)
    d.ellipse([cx - r + st, cy - r + st, cx + r - st, cy + r - st], fill=WHITE)


def _cloud(d, x, y, s, st, dy=0.0):
    y += dy * s
    ell = [(0.04, 0.46, 0.44, 0.86), (0.24, 0.20, 0.70, 0.70), (0.54, 0.40, 0.96, 0.86)]
    rect = (0.24, 0.60, 0.76, 0.86)
    for inset, fill in ((0, BLACK), (st, WHITE)):
        for a, b, c, e in ell:
            d.ellipse([x + a * s + inset, y + b * s + inset,
                       x + c * s - inset, y + e * s - inset], fill=fill)
        a, b, c, e = rect
        d.rectangle([x + a * s, y + b * s + inset, x + c * s, y + e * s - inset], fill=fill)


def icon(d, kind, x, y, s):
    st = max(2 * S, s * 0.055)
    if kind == "sun":
        _sun(d, x + s / 2, y + s / 2, s * 0.22, st)
    elif kind == "partly":
        _sun(d, x + s * 0.66, y + s * 0.34, s * 0.16, st)
        _cloud(d, x, y + s * 0.08, s * 0.86, st)
    elif kind == "cloud":
        _cloud(d, x, y, s, st)
    elif kind == "fog":
        _cloud(d, x, y, s, st, dy=-0.16)
        for i, (a, b) in enumerate(((0.12, 0.88), (0.22, 0.78))):
            yy = y + s * (0.82 + 0.13 * i)
            d.line([x + a * s, yy, x + b * s, yy], fill=BLACK, width=int(st))
    elif kind == "rain":
        _cloud(d, x, y, s, st, dy=-0.14)
        for fx in (0.30, 0.50, 0.70):
            d.line([x + fx * s, y + s * 0.80, x + (fx - 0.07) * s, y + s * 0.98],
                   fill=BLACK, width=int(st))
    elif kind == "snow":
        _cloud(d, x, y, s, st, dy=-0.14)
        r = s * 0.045
        for fx, fy in ((0.28, 0.84), (0.50, 0.93), (0.72, 0.84)):
            d.ellipse([x + fx * s - r, y + fy * s - r, x + fx * s + r, y + fy * s + r],
                      fill=BLACK)
    elif kind == "thunder":
        _cloud(d, x, y, s, st, dy=-0.14)
        pts = [(0.52, 0.62), (0.36, 0.84), (0.48, 0.84), (0.40, 1.02),
               (0.66, 0.76), (0.53, 0.76), (0.62, 0.62)]
        d.polygon([(x + a * s, y + b * s) for a, b in pts], fill=BLACK)


# ---------- layout ----------

def deg(v):
    n = int(round(v))
    return "%d°" % (0 if n == 0 else n)  # avoid "-0°"


def clock(dt, cfg):
    if cfg.get("clock_24h", True):
        return dt.strftime("%H:%M")
    return dt.strftime("%I:%M %p").lstrip("0")


def render(cfg, data):
    """Current conditions on top, then one row per day for the next 10 days.

    The layout is designed for 600 x 800 and scales to other sizes. Nothing is
    drawn below `safe_height` (defaults to the full height).
    """
    W, H = cfg["width"], cfg["height"]
    SAFE = min(cfg.get("safe_height", H), H)
    img = Image.new("L", (W * S, H * S), WHITE)
    d = ImageDraw.Draw(img)
    p = lambda v: v * S          # final px -> working px
    fx, fy = W / 600.0, SAFE / 800.0
    f = min(fx, fy)              # font / icon scale
    y = lambda v: v * fy         # reference y -> final px
    M = 24 * fx                  # side margin

    def rule(yy, colour=BLACK, width=1):
        d.line([p(M), p(yy), p(W - M), p(yy)], fill=colour, width=width * S)

    # local time at the forecast location, as a naive datetime
    now = (datetime.now(timezone.utc).replace(tzinfo=None)
           + timedelta(seconds=data.get("utc_offset_seconds", 0)))
    cur, daily = data["current"], data["daily"]
    label, kind = describe(cur["weather_code"])

    # header
    d.text((p(M), p(y(26))), cfg["place"], font=font("bold", 26 * f), fill=BLACK, anchor="lm")
    d.text((p(W - M), p(y(26))), now.strftime("%a %d %b") + "  ·  updated " + clock(now, cfg),
           font=font("regular", 18 * f), fill=GREY, anchor="rm")
    rule(y(50))

    # current conditions
    isz = 170 * f
    icon(d, kind, p(M), p(y(62)), p(isz))
    tx = M + isz + 24 * fx
    d.text((p(tx), p(y(128))), deg(cur["temperature_2m"]), font=font("bold", 120 * f),
           fill=BLACK, anchor="lm")
    d.text((p(tx), p(y(212))), label, font=font("bold", 30 * f), fill=BLACK, anchor="lm")
    wind_unit = data.get("current_units", {}).get("wind_speed_10m", "km/h")
    today = "Today  %s / %s   Rain %d%%" % (
        deg(daily["temperature_2m_max"][0]), deg(daily["temperature_2m_min"][0]),
        daily["precipitation_probability_max"][0] or 0)
    d.text((p(M), p(y(264))), today, font=font("regular", 22 * f), fill=BLACK, anchor="lm")
    d.text((p(W - M), p(y(264))),
           "Feels %s  ·  Wind %d %s" % (deg(cur["apparent_temperature"]),
                                         round(cur["wind_speed_10m"]), wind_unit),
           font=font("regular", 19 * f), fill=GREY, anchor="rm")
    rule(y(290), width=2)

    # next 10 days: day, icon, rain chance, low ---bar--- high
    days = list(range(1, min(11, len(daily["time"]))))
    if not days:
        return img.resize((W, H), Image.LANCZOS), now
    top, bottom = y(294), SAFE - 4 * fy
    rh = (bottom - top) / len(days)
    lows = [daily["temperature_2m_min"][i] for i in days]
    highs = [daily["temperature_2m_max"][i] for i in days]
    lo_all, hi_all = min(lows), max(highs)
    span = max(hi_all - lo_all, 1.0)
    bx0, bx1 = 350 * fx, 486 * fx            # temperature range bar
    bar_h = 10 * f
    row_font, small_font = font("bold", 23 * f), font("regular", 21 * f)
    isz = min(rh * 0.82, 44 * f)

    for n, i in enumerate(days):
        cy = top + rh * (n + 0.5)
        day = datetime.strptime(daily["time"][i], "%Y-%m-%d")
        d.text((p(M), p(cy)), day.strftime("%a %d").replace(" 0", " "), font=row_font,
               fill=BLACK, anchor="lm")
        icon(d, describe(daily["weather_code"][i])[1],
             p(168 * fx - isz / 2), p(cy - isz / 2), p(isz))
        rain = daily["precipitation_probability_max"][i]
        if rain is not None and rain >= 10:
            d.text((p(262 * fx), p(cy)), "%d%%" % rain, font=small_font, fill=GREY, anchor="mm")
        lo, hi = lows[n], highs[n]
        d.text((p(bx0 - 10 * fx), p(cy)), deg(lo), font=small_font, fill=BLACK, anchor="rm")
        d.text((p(bx1 + 10 * fx), p(cy)), deg(hi), font=row_font, fill=BLACK, anchor="lm")
        d.line([p(bx0), p(cy), p(bx1), p(cy)], fill=200, width=2 * S)
        x0 = bx0 + (lo - lo_all) / span * (bx1 - bx0)
        x1 = max(bx0 + (hi - lo_all) / span * (bx1 - bx0), x0 + bar_h)
        d.rounded_rectangle([p(x0), p(cy - bar_h / 2), p(x1), p(cy + bar_h / 2)],
                            radius=p(bar_h / 2), fill=BLACK)
        if n < len(days) - 1:
            rule(top + rh * (n + 1), colour=210)

    return img.resize((W, H), Image.LANCZOS), now


HTML = """<html>
<head>
<meta http-equiv="Content-Type" content="text/html; charset=utf-8">
<meta http-equiv="refresh" content="{refresh}">
<meta name="viewport" content="width=device-width, initial-scale=1">
<title>Weather</title>
<style>
html, body {{ margin: 0; padding: 0; background: #fff; }}
img {{ display: block; width: 100%; border: 0; }}
</style>
</head>
<body><img src="weather.png?t={stamp}" alt="Weather"></body>
</html>
"""


def main():
    with open(os.path.join(ROOT, "config.json")) as fh:
        cfg = json.load(fh)
    # Location comes from GitHub secrets (LATITUDE / LONGITUDE) so it isn't in the public repo.
    for key in ("latitude", "longitude"):
        env = os.environ.get(key.upper(), "").strip()
        if env:
            cfg[key] = float(env)
    if "--sample" not in sys.argv and ("latitude" not in cfg or "longitude" not in cfg):
        raise SystemExit("Set the LATITUDE and LONGITUDE repository secrets.")
    data = sample() if "--sample" in sys.argv else fetch(cfg)
    img, now = render(cfg, data)
    out = os.path.join(ROOT, "site")
    os.makedirs(out, exist_ok=True)
    img.save(os.path.join(out, "weather.png"), optimize=True)
    with open(os.path.join(out, "index.html"), "w") as fh:
        fh.write(HTML.format(refresh=cfg.get("refresh_seconds", 900), stamp=int(time.time())))
    print("Wrote site/weather.png and site/index.html (%s)" % now.strftime("%Y-%m-%d %H:%M"))


if __name__ == "__main__":
    main()

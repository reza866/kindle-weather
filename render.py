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
        "hourly": "temperature_2m,weather_code,precipitation_probability",
        "daily": "weather_code,temperature_2m_max,temperature_2m_min,"
                 "precipitation_probability_max",
        "timezone": "auto",
        "forecast_days": 5,
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
    hours = [now + timedelta(hours=i) for i in range(48)]
    days = [now.date() + timedelta(days=i) for i in range(5)]
    codes = [2, 61, 3, 71, 95]
    return {
        "utc_offset_seconds": 0,
        "current": {"time": now.strftime("%Y-%m-%dT%H:%M"), "temperature_2m": -3.4,
                    "apparent_temperature": -7.1, "weather_code": 2,
                    "wind_speed_10m": 14.2},
        "current_units": {"wind_speed_10m": "km/h"},
        "hourly": {"time": [h.strftime("%Y-%m-%dT%H:%M") for h in hours],
                   "temperature_2m": [10 - i % 14 for i in range(48)],
                   "weather_code": [[0, 2, 3, 45, 61, 71, 95][i % 7] for i in range(48)],
                   "precipitation_probability": [(i * 7) % 100 for i in range(48)]},
        "daily": {"time": [d.isoformat() for d in days],
                  "weather_code": codes,
                  "temperature_2m_max": [12.3, 9.8, 7.1, 1.2, 14.0],
                  "temperature_2m_min": [4.1, 2.2, -1.5, -6.0, 8.3],
                  "precipitation_probability_max": [20, 80, 40, 90, 60]},
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


def hour_label(dt, cfg):
    if cfg.get("clock_24h", True):
        return dt.strftime("%H:00")
    return dt.strftime("%I %p").lstrip("0")


def render(cfg, data):
    W, H, SAFE = cfg["width"], cfg["height"], min(cfg["safe_height"], cfg["height"])
    img = Image.new("L", (W * S, H * S), WHITE)
    d = ImageDraw.Draw(img)
    p = lambda v: v * S  # final px -> working px
    k = SAFE / 560.0     # vertical scale relative to the reference layout
    kw = W / 600.0
    f = min(k, kw)       # font / icon scale
    M = 24 * kw          # side margin

    # local time at the forecast location, as a naive datetime
    now = (datetime.now(timezone.utc).replace(tzinfo=None)
           + timedelta(seconds=data.get("utc_offset_seconds", 0)))
    cur, hourly, daily = data["current"], data["hourly"], data["daily"]
    label, kind = describe(cur["weather_code"])

    # header
    d.text((p(M), p(22 * k)), cfg["place"], font=font("bold", 24 * f), fill=BLACK, anchor="lm")
    d.text((p(W - M), p(22 * k)), now.strftime("%a %d %b") + "  ·  updated " + clock(now, cfg),
           font=font("regular", 17 * f), fill=GREY, anchor="rm")
    d.line([p(M), p(42 * k), p(W - M), p(42 * k)], fill=BLACK, width=S)

    # current conditions
    isz = 170 * f
    icon(d, kind, p(M), p(52 * k), p(isz))
    tx = M + isz + 22 * kw
    d.text((p(tx), p(118 * k)), deg(cur["temperature_2m"]), font=font("bold", 118 * f),
           fill=BLACK, anchor="lm")
    d.text((p(tx), p(196 * k)), label, font=font("bold", 28 * f), fill=BLACK, anchor="lm")
    wind_unit = data.get("current_units", {}).get("wind_speed_10m", "km/h")
    line = "High %s   Low %s   Rain %d%%" % (
        deg(daily["temperature_2m_max"][0]), deg(daily["temperature_2m_min"][0]),
        daily["precipitation_probability_max"][0] or 0)
    d.text((p(M), p(246 * k)), line, font=font("regular", 22 * f), fill=BLACK, anchor="lm")
    d.text((p(W - M), p(246 * k)),
           "Feels %s  ·  Wind %d %s" % (deg(cur["apparent_temperature"]),
                                         round(cur["wind_speed_10m"]), wind_unit),
           font=font("regular", 18 * f), fill=GREY, anchor="rm")
    d.line([p(M), p(270 * k), p(W - M), p(270 * k)], fill=BLACK, width=S)

    # next hours: every 3 hours after now
    cur_t = datetime.strptime(cur["time"], "%Y-%m-%dT%H:%M")
    times = [datetime.strptime(t, "%Y-%m-%dT%H:%M") for t in hourly["time"]]
    idx = [i for i, t in enumerate(times) if t > cur_t][::3][:5]
    col = (W - 2 * M) / 5.0
    for n, i in enumerate(idx):
        cx = M + col * (n + 0.5)
        d.text((p(cx), p(290 * k)), hour_label(times[i], cfg), font=font("regular", 18 * f),
               fill=BLACK, anchor="mm")
        s = 56 * f
        icon(d, describe(hourly["weather_code"][i])[1], p(cx - s / 2), p(302 * k), p(s))
        d.text((p(cx), p(378 * k)), deg(hourly["temperature_2m"][i]), font=font("bold", 24 * f),
               fill=BLACK, anchor="mm")
        pr = hourly["precipitation_probability"][i]
        if pr is not None and pr >= 20:
            d.text((p(cx), p(401 * k)), "%d%%" % pr, font=font("regular", 15 * f),
                   fill=GREY, anchor="mm")
    d.line([p(M), p(416 * k), p(W - M), p(416 * k)], fill=BLACK, width=S)

    # next days
    days = list(range(1, min(5, len(daily["time"]))))
    col = (W - 2 * M) / float(len(days))
    for n, i in enumerate(days):
        cx = M + col * (n + 0.5)
        day = datetime.strptime(daily["time"][i], "%Y-%m-%d")
        d.text((p(cx), p(436 * k)), day.strftime("%a"), font=font("bold", 20 * f),
               fill=BLACK, anchor="mm")
        s = 60 * f
        icon(d, describe(daily["weather_code"][i])[1], p(cx - s / 2), p(448 * k), p(s))
        d.text((p(cx), p(530 * k)),
               "%s / %s" % (deg(daily["temperature_2m_max"][i]), deg(daily["temperature_2m_min"][i])),
               font=font("regular", 20 * f), fill=BLACK, anchor="mm")

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

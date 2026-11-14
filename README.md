# Kindle weather display

Turns an old Kindle with a damaged lower screen into a weather display. A GitHub Actions job draws the forecast as one black-and-white image every 30 minutes and publishes it to GitHub Pages. The Kindle's built-in browser just shows that page and reloads it every 15 minutes.

Nothing is installed on your computer: the image is drawn on GitHub's servers with Pillow 13.0.0, pinned by hash in `requirements.txt`.

## Settings (`config.json`)

| Key | Meaning |
| --- | --- |
| `place` | Name shown at the top. Shown on a public page, so pick something you're happy to share. |
| `LATITUDE`, `LONGITUDE` | Not in this file: they are repository secrets (**Settings → Secrets and variables → Actions**) so the location stays out of the public code. Two decimals is plenty. |
| `temperature_unit` | `"celsius"` or `"fahrenheit"`. |
| `clock_24h` | `true` for 14:00, `false` for 2 PM. |
| `width`, `height` | Kindle screen size in pixels: 600×800 for most basic Kindles, 758×1024 or 1072×1448 for Paperwhites. |
| `safe_height` | Pixels from the top that still work. Everything is drawn above this line, and the rest stays white. |
| `refresh_seconds` | How often the Kindle reloads the page. |

Weather data comes from [Open-Meteo](https://open-meteo.com), which is free and needs no API key.

## Publish

1. Create a GitHub repository and push these files.
2. Repository **Settings → Pages → Source: GitHub Actions**.
3. **Actions → Update weather → Run workflow**. When it finishes, the page is at `https://<user>.github.io/<repo>/`.

The page is public. Free GitHub accounts can only publish Pages from public repositories.

## Kindle setup

1. **Settings → Device Options → Device Info** shows the model and firmware. Set `width`/`height` to match.
2. Open the browser (**Menu → Experimental Browser** or **Web Browser**), go to the page URL, and bookmark it.
3. Keep the screen from sleeping: type `~ds` in the Kindle search bar and press Enter. This lasts until the next restart, and some newer firmware ignores it.
4. Keep it plugged in. Wi-Fi stays on, so the battery lasts a day or two at most.

If the old browser can't open the page, or the screen won't stay awake, the fallback is to jailbreak the Kindle and have it download `weather.png` directly. The cloud side stays the same.

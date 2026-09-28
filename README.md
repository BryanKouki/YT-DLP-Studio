<p align="center">
  <picture>
    <source media="(prefers-color-scheme: dark)" srcset="assets/logo_dark.png">
    <img src="assets/logo.png" alt="YT-DLP Studio" width="520">
  </picture>
</p>

<p align="center">
  A clean desktop GUI for <a href="https://github.com/yt-dlp/yt-dlp">yt-dlp</a> and FFmpeg: download audio and video, manage a download queue, and convert or compress local files without touching the command line.
</p>

---

## Features

**Audio**
- Download a single track, many links at once (one per line), or a whole playlist/album
- Formats: MP3, M4A, AAC, Opus, Vorbis, FLAC, ALAC, WAV; bitrate from 32 to 320 kbps (320 kbps by default)
- Title, artist and duration are fetched in the background as soon as you paste a link. You can hit **Download** before the lookup finishes.
- Embedded metadata and cover art, with the cover always center-cropped to **1:1**
- Playlists go into their own folder named after the playlist, with the playlist cover saved as `playlistcover.jpg`
- **Playlist availability check** lists every unavailable track with its position and neighbours, without downloading anything

**Video**
- Resolution up to 4320p (8K), FPS cap, preferred video/audio codec (H.264, H.265, VP9, AV1, VP8 / AAC, Opus, MP3, FLAC)
- Automatic fallback to the best available format when the exact combination doesn't exist
- MP4/MKV container, subtitles (download + embed), chapters
- Files are named `Title - Channel`

**Convert & compress**
- Convert any local file to MP3, M4A, Opus, FLAC, WAV, MP4 (H.264), MKV (H.265) or WEBM (VP9)
- Quality presets, plus a max-resolution option that only downscales and never upscales
- **Target-size compressor**: type `25 MB` or `1.5 GB` and the bitrate is calculated to fit that size

**General**
- Trim a section of the media before downloading (range slider or HH:MM:SS fields)
- Download queue with per-item progress and a live log
- yt-dlp and FFmpeg are downloaded automatically on first run and can be updated with one click
- Portable: settings and binaries live in a `data/` folder next to the executable
- English / Portuguese (BR) interface, dark and light themes
- Built-in quick guide (the **?** button)

## Getting started

### Option 1: build the `.exe` (Windows)

1. Install [Python 3.10+](https://www.python.org/downloads/) and tick **"Add python.exe to PATH"**.
2. Double-click **`build.bat`**.
3. Your executable is at **`dist\YT-DLP Studio.exe`**. It is a single file and can be moved anywhere.

The first launch downloads yt-dlp (~15 MB) and FFmpeg (~80 MB). You can watch the progress in the **Queue & Log** tab.

### Option 2: run from source

```bash
python -m venv .venv
.venv\Scripts\activate        # Linux/macOS: source .venv/bin/activate
pip install -r requirements.txt
python src/main.py
```

### Self-check

```bash
python src/selfcheck.py
```

This runs offline tests for the converter command builder, the playlist cover template and the playlist availability parser.

## Default folders

| Type  | Location                         |
|-------|----------------------------------|
| Music | `%USERPROFILE%\Music\Download`   |
| Video | `%USERPROFILE%\Videos\Download`  |

Both paths resolve to the current Windows user automatically, and both can be changed in **Settings → Folders**.

## Project structure

```
build.bat            builds the .exe with PyInstaller
requirements.txt
make_logo.py         regenerates the logo/icon
assets/              icon, logo, red/black/white CustomTkinter theme
docs/                user manual + technical documentation (PDF, Portuguese)
docs_src/            scripts that generate the PDFs (ReportLab)
src/
  main.py            entry point, main window
  tabs.py            Audio and Video tabs
  converter_tab.py   Convert & compress tab
  queue_tab.py       Queue & Log tab
  downloader.py      yt-dlp command builder, queue worker, playlist check
  dependencies.py    downloads/updates yt-dlp and FFmpeg
  settings_dialog.py settings window
  settings_store.py  settings.json persistence
  help_dialog.py     built-in quick guide
  i18n.py            EN / PT-BR strings
  theme.py, widgets.py
  selfcheck.py       offline tests
```

The technical PDF in `docs/` explains every module and how to add formats, options or languages.

## Credits

- [yt-dlp](https://github.com/yt-dlp/yt-dlp) does all the downloading
- [FFmpeg](https://ffmpeg.org/) handles conversion, merging, cover art and compression
- [CustomTkinter](https://github.com/TomSchimansky/CustomTkinter) provides the UI

## Disclaimer

YT-DLP Studio is a graphical front-end for yt-dlp. It does not host, store or distribute any content, and it does not bypass DRM. Only download content you have the right to access, and respect the Terms of Service of each platform and the copyright of creators.

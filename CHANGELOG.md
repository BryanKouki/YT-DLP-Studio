# Changelog

## v1.3.3

### Added
- Every browser yt-dlp can read cookies from is now listed: Firefox, Safari (macOS), Edge, Chrome, Brave, Chromium, Opera, Vivaldi and Whale.
- Chromium-based browsers show a warning: on Windows they encrypt cookies in a way yt-dlp may not be able to read (DPAPI error), even with the browser closed.

### Changed
- Firefox is now the default browser for cookies, since yt-dlp reads it without the Windows decryption problem. A browser chosen before is kept.

## v1.3.2

### Fixed
- When browser cookies could not be read, every item in the queue failed one after another. Now the option is turned off automatically and the same item is downloaded again without cookies, so nothing in the queue is lost.

### Added
- If the chosen browser is open (Edge keeps running in the background even with no windows), the app asks before closing it to read the cookies.
- Pasting a copied Log into the link box extracts the links from its "Iniciando:" lines, to queue them again.

### Changed
- The Log explains which cookie error happened: the browser was open, or its cookies are encrypted in a way yt-dlp cannot open yet (closing the browser does not help in that case). yt-dlp says "Chrome" in this message even for Edge.
- The cookies option now says the browser must be closed, including in the background.

## v1.3.1

### Added
- Remove a single item from the queue with the X on the right of it. If that item is downloading, the download is canceled first and the queue moves on to the next item.
- Start a single item from the queue with the ▶ next to it. With the queue stopped, only that item is downloaded; with the queue running, it becomes the next one. On a failed or canceled item, ▶ tries it again.

### Changed
- More formal wording in notices, confirmations and Log hints (for example "Next: ..." and "Could not identify the link. It can still be downloaded.").

## v1.3.0

### Added
- New interface: a sidebar with the four sections, cards, icons, light and dark themes, and animations for confirmations, dialogs, queue items and progress bars. Every previous feature is still there.
- Floating notices confirm actions (added to queue, download finished, settings saved, copied, errors).
- The link box shows what it found right after you paste: "Playlist: name", "Track: title" or "N links". For playlists, Title and Artist are hidden.
- The current download and the number of pending items are visible from any section, in the sidebar.
- "Save each track's cover" option: keeps a cover file next to every track of a playlist.
- When playlist tracks fail, choose when the queue pauses: after each playlist, at the end of the queue (review one playlist at a time), or never.
- In the failed tracks list, clicking a track name copies "Song - Artist".
- Ctrl+Enter in the link box starts the download.

### Changed
- Adding to the queue or starting a download no longer switches to the Queue screen; the link box is cleared for the next link.
- Queue items show the playlist name, named in the background if added before the lookup finished.
- Faster link lookup for playlists.
- The destination folder only receives finished files; temporary files stay in `data\tmp`.
- The layout fits the minimum window size (840x620) without a scrollbar on the Audio and Video sections.

### Fixed
- "Save thumbnail" on a playlist downloaded every track's cover into the folder and deleted them at the end. Now only the playlist cover is downloaded.
- Several playlists queued in a row could all be labelled with the first one's title and artist.

## v1.2.0

### Added
- Failed tracks and replacements: when tracks of a playlist fail, the queue pauses and lists them with their position, title, reason and a link you can copy whole or by ID. A replacement link is downloaded into the same folder with file dates set so it sits exactly between the neighbouring tracks.
- Browser cookies against YouTube's "Sign in to confirm you're not a bot" block. Microsoft Edge is the default; Google Chrome asks for two confirmations.
- The Log explains known errors: cookies that could not be read, and the "not a bot" block.

### Changed
- A playlist where only some tracks failed is marked "Done — N failed track(s)" and still gets its playlist cover.

### Notes
- yt-dlp may not be able to read cookies from recent Edge and Chrome versions on Windows. Chrome must also be closed while downloading.

## v1.1.0

### Added
- Tauri + TypeScript version of the app in the `tauri/` folder: a single 4 MB `.exe` with the same features as the Python version.
- Error lines in the Log are shown in red (Tauri version).

### Fixed
- Progress bars stayed at 0% and jumped to 100% at the end of a download; yt-dlp is now called with `--progress`.
- The dependency status showed "~~15MB" / "~~80MB" with a doubled tilde (Python version).

### Changed
- Percentage lines no longer flood the Log.
- Titles with accents or non-Latin characters are read correctly from yt-dlp (Tauri version).

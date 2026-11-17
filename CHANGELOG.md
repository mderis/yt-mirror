# Changelog

All notable changes to this project are documented in this file.
The format follows [Keep a Changelog](https://keepachangelog.com/en/1.1.0/) and the project uses [Semantic Versioning](https://semver.org/).

## [Unreleased]

### Added
- Exact dates (milestone M4): videos whose date is only approximate get their exact date in the background, newest first. Each date shows whether it waits, is being fetched (a turning icon) or could not be fetched (a warning that says why and when it is tried again). The channel page says "Exact dates 340 of 1,000" and, once measured, how long it takes. In the sidebar this is background work: it shows only when the channel has no new videos and no failed check to report.
- Without a key, exact dates are looked up one at a time and at most 300 lookups an hour, together with the lookups of downloads, so YouTube's "not a bot" check stays away; after such a check the pace is halved until midnight. Downloads always go first. The number of lookups of each hour is written to the log.
- The optional YouTube API key: a guide in the app explains how to get a free key, with "Test key", "Save key" and "Remove key". With a key, a channel's exact dates arrive in seconds, also during YouTube's "not a bot" check. The key is kept only on this Mac, in a file of the data folder that only you can read, and never in the database, the logs or a report. A key that stops working, runs out of its daily quota or cannot be read is done without, with a notice next to the progress and no dialog.
- When fetching the dates of a channel would take more than 10 minutes, the channel offers the key with the measured time.
- Automatic checks: all channels are checked when the app opens and every 30 minutes, a channel is checked when you select it after more than 5 minutes, a failed check is tried again after 5, 15 and 60 minutes, and a full check runs by itself once a week, one channel at a time and never while that channel downloads. The sidebar says "Checking channels: 3 of 5", and a failed channel "Could not check · retrying in 5 min".
- Every check sets the dates of downloaded files back to the published time where they differ, and "Repair dates" in the channel menu does it on demand.
- When a video gets a new title on YouTube, its file is renamed at the next check, never over another file, and keeps its dates. A file named after its video ID because its title had no usable characters gets its title once it has one.
- Downloads (milestone M3): "Mirror" on a video downloads it as an MKV file named after its title, in the folder of its channel. Pressing Mirror on several videos puts them in line, and they download one after another. The file has the title, the channel, the description, the exact published time, the address and ID of the video, its chapters, English subtitles (the creator's, else the auto-generated ones, labelled as such) and the thumbnail as its cover inside. The complete metadata and the original thumbnail are also kept in the hidden `.yt-mirror` folder.
- Both dates of every downloaded file, created and modified, are the moment the video became public on YouTube (for a premiere, when it was shown), and are read back to make sure. Finder sorts the folder in the order of the channel.
- A download shows its progress in its row: the stage, the percent, the quality, the speed and the time left. The channel says "Mirroring 2 of 3". A synced video shows its quality and size, and has Play (in your own video player) and Show in Finder.
- Cancel stops a download that waits, downloads or is being processed, and leaves nothing behind. A failed download says why in its row and offers Retry. If only the subtitles fail, the video is saved without them.
- The details panel of a video: its file, formats, dates, description and chapters, with Play, Show in Finder and Open on YouTube.
- When the exact date of a video arrives, it replaces the approximate one with a short highlight.
- Removing a channel offers "Keep the files" or "Delete the files". Deleting moves only the files yt-mirror made to the Trash, says how many and how much room, and leaves your own files in the folder.
- The JavaScript challenge solver of yt-dlp is installed with it, so YouTube offers every format.
- Every channel folder names its channels in `.yt-mirror/channel.json` (ID, handle, title), so that a later version can link a folder to its channels again. A folder that two channels share lists both.
- Channels (milestone M2): paste a channel link, a handle or a channel ID, see the channel before you add it, and choose its folder, its quality and what to mirror. A link to a video or a playlist is refused with a sentence that says what is accepted. The quality and "what to mirror" are stored now and take effect with the downloads of the next milestones.
- The catalogue of a channel: every regular video with its thumbnail, title, duration, views and date, read from YouTube in the background. A large channel shows how many videos were found so far, and the app can be used meanwhile.
- Checks: "Check now" reads only the top of a channel and takes a few seconds. "Full check" in the channel menu reads the whole channel, shows its progress and can be cancelled. New videos are marked as new. A video counts as removed from YouTube only after two full checks in a row without it, and it stays in the list.
- Approximate dates: the list of a channel gives dates only roughly ("2 years ago"). They are shown as far as they are known ("around 2024", "around Mar 2026") and look like placeholders until the exact date is known.
- The sidebar with every channel, its status and its count of new videos, "Check all channels now" and the free space of the disk the library is on. The app opens on the channel that was open last.
- The channel menu, by a right-click and by "More actions": check now, full check, pause and resume, open the folder, open on YouTube, remove. Removing a channel asks first, and its folder stays.
- Thumbnails and avatars are kept on your Mac, so the list also works offline.
- When YouTube asks to confirm that you are not a bot, the app pauses what it asks of YouTube by itself, shows one banner that says what you can try, and goes on by itself later or with "Try now".
- A failed check shows a banner with "Try again" and the time it failed, and keeps the list of the last successful check. While it is tried again, the channel says "Checking", the banner says so and its button is busy.
- "Waiting for YouTube": while the app pauses after YouTube's "not a bot" check, a channel that is still to be listed says so, with the time of the next attempt.
- "Check all channels now" waits 1 to 3 seconds between two channels, so YouTube is not asked in a burst.
- A video that two channels list belongs to the channel that listed it first, and is never counted as new in the other one.
- A native Mac app (milestone M1): `./start` builds a real app bundle on your Mac and starts the app through it. The running app is "yt-mirror" with its own icon in the Dock, the app switcher, the menu bar and Activity Monitor, and no longer "Python". A clone is "yt-mirror (dev)", so it can run next to an installed copy.
- The app's own menu bar, so far with the app menu and Edit: Undo, Redo, Cut, Copy, Paste and Select All work in text fields.
- Only one yt-mirror runs per data folder. Starting it again brings the open window to the front.
- The first-run screen: it shows the tools yt-mirror needs (Python, yt-dlp, ffmpeg, Deno), downloads the missing ones into the app folder with a progress bar, checks every download against its checksum, and offers "Try again" for a step that failed.
- ffmpeg has a second download source that is used when the first one fails. `./start --doctor` says which source a tool came from.
- The tools are checked at every start. A tool that is missing or stopped working gets a banner with an "Install now" button.
- Live updates in the window: the interface follows a download as it happens.
- The app folder can be moved or copied: the Python environment and the app bundle are rebuilt at the next start.

### Fixed
- A download showed a bar that did not move, without a percent, or "Processing" from its first second. The percent is now one for the whole video, its video and audio streams together, and the bar fills with it. When YouTube gives no size, the row says how much has arrived. While a video is processed, the bar shows that the step runs, without a percent.
- A file that the Trash refuses no longer stops the removal of a channel halfway: the other files go, the channel is removed, and the app lists the files left in the folder. Removing a channel stops its checks and downloads first, so nothing is written into its folder meanwhile.
- The library folder and a folder you chose are never moved to the Trash with a channel, even when empty. Only a folder yt-mirror created may go.
- A `channel.json` that yt-mirror cannot read, or that a newer version wrote, is never replaced or moved to the Trash.
- A side file of a downloaded video (its metadata or a thumbnail) that cannot be written no longer fails the video: it is written later. A failure after the file is in the channel folder takes it out again, so nothing unfinished is left there.
- A start after a crash moves a half-placed file to the Trash only when the video ID inside it is that download, and a Trash that refuses no longer stops the app from starting.
- Quitting stops the ffmpeg that a download started, so the download is cleaned up before the app ends.
- A database update that fails changes nothing; before, part of it could stay and the next start failed. Before every database update the app now keeps a copy of the database in `data/backups/` (the five newest). If an update fails, yt-mirror says so, names the copy, and does not start.
- A check and a download that store their results at the same moment no longer fail with "database is locked": one waits for the other.
- Once a video is stored as synced its file is never moved or deleted again, even when telling the window about it fails. Its side files are stored with it, so a crash right after loses none.
- Quitting during a merge or the embedding of subtitles cancels the download; before, the video ended as failed, or a second download started during the quit. Cancel stops the ffmpeg of that download at once.
- In a folder that several channels share, a new download never takes a name another channel still tracks, and "Delete the files" moves a video file only when the video inside it is the channel's.
- Removing a channel whose download or check does not stop in time keeps the channel and its files, and says so. Its waiting checks are dropped by then and, once no check runs, its downloads are cancelled; they do not start again by themselves.
- Cancel answers within half a second at every stage. A download that only asks YouTube for its details, before any file is written, ends at once; before, Cancel waited for YouTube's answer, several seconds. A download that writes files shows "Cancelling…" until it has cleaned up.
- A cancelled or failed download now says so only once its temp files are gone. A temp folder that cannot be removed no longer turns a cancel into a failure: a warning is logged and the next start removes it.
- A video removed from YouTube no longer offers Mirror or Retry, in its row or its details; a failed one still says why. A downloaded one still plays and shows in Finder. A download that waits when a check finds its video removed ends at that moment; one that runs goes on. The buttons come back when a check lists the video again.
- Radio buttons are drawn by yt-mirror in the colours of its theme. In the dark theme the system drew them as white discs. They keep the keyboard, the labels and VoiceOver of the system, and follow "Increase contrast" and "Reduce motion".
- A start cleans up what a quit left on a drive that was not connected once the drive is back, and removes temp folders of downloads that ended. Pressing Mirror before such a restart cleans up first, so the new file gets its own name; while the drive is still away, the download fails with "The folder is not available" and the cleanup waits for the drive.
- A video whose YouTube description holds half an emoji no longer leaves an unfinished file in the channel folder: its metadata is saved as it is.
- "Delete the files" names every file it leaves in the folder, with why: macOS refused it, another video is inside, its video could not be checked, or it leads outside the folder. A file that cannot be checked no longer stops the removal halfway.
- A database file that cannot be read gets its own message; repeated failed starts no longer push older database copies out.
- Quitting with Cmd+Q, from the Dock, with Ctrl+C or with a termination signal now shuts the app down cleanly. Before, only closing the window did: the other ways ended the app without stopping its server and without the last log line.

### Added in milestone M0
- The project skeleton (milestone M0): `./start` prepares its own Python environment inside the app folder, builds the interface, and opens the app window with a placeholder page. Flags `--dev`, `--debug`, `--browser`, `--doctor`.
- The local server with its security checks: it listens on 127.0.0.1 only, rejects other origins, and requires a session token on every API call.
- Structured debug logs in `data/logs/`, one file per day, kept 14 days, with secrets removed.
- The database with migrations, and the settings table.
- The theme center: every colour, font, size, radius, shadow and animation duration is a named token in one folder, with a light and a dark theme, a lint check that allows only tokens, and a theme preview page for development.
- A convention for tests: each one names the requirement whose behaviour it verifies, or is marked `infra` when it verifies no product behaviour at all. Behaviour without a requirement is added to the specification first.
- An error code and user text for the case that the window cannot reach the app's own server.
- Automated checks on every pull request: lint, types, layer rules, tests with coverage thresholds, end-to-end tests in WebKit and Chromium with screenshots in both themes, and a smoke test that starts a fresh clone on macOS 15 and 26.
- Complete planning package for version 1: product specification, architecture, designs for every screen, test strategy, logging specification, release and update design, coding standards, glossary, decision records, implementation plan and open questions.

# yt-mirror: Glossary

Use these words, with these meanings, in code, UI text, logs, tests and docs. If a new concept appears, add it here first.

| Term | Meaning | In code |
|---|---|---|
| **Channel** | A YouTube channel the user added | `Channel` |
| **Video** | One regular video of a channel. Shorts and live streams are not videos in V1 | `Video` |
| **Catalogue** | The app's stored list of a channel's videos | `catalogue` |
| **Listing** | Reading the channel's video list from YouTube | `list_channel` |
| **Check** | One refresh of a channel's catalogue: listing plus everything that follows from it | `check` |
| **Mirror** (verb) | Download a video so that a correct file exists for it | `mirror`, job kind `download` |
| **Auto-mirror** | Per-channel option: mirror every eligible video now and after each check | `auto_mirror` |
| **Synced** | The video has a verified local file with correct metadata and dates | status `synced` |
| **Not downloaded** | The video has no local file and is not queued | status `not_downloaded` |
| **Queued** | Waiting for a download slot | status `queued` |
| **Downloading** | Video or audio data is being transferred | status `downloading` |
| **Processing** | Merging, embedding metadata, verifying, setting dates | status `processing` |
| **Failed** | The last attempt ended with an error | status `failed` |
| **File missing** | The video was synced, but its file is no longer where it should be | status `file_missing` |
| **Excluded** | The user (or a rule) decided this video must never be mirrored | flag `excluded` |
| **Restore** | Undo an exclusion | `restore` |
| **Auto-exclude rule** | A per-channel rule that excludes matching videos | `ExcludeRule` |
| **Exception** | A video the user protected from auto-exclude rules | `exclude_exception` |
| **New** | First seen in a check after the channel's first listing, and still relevant (R-CH-15) | derived `is_new` |
| **Removed from YouTube** | No longer listed on the channel after two successful checks | flag `gone` |
| **Published time** | The moment the video became public on YouTube | `published_at` |
| **Exact date / approximate date** | Whether the published time is known to the second or only roughly | `published_exact` |
| **Library** | The default parent folder for channel folders | `library` |
| **Channel folder** | The folder that holds one channel's video files | `folder` |
| **Hidden folder** | The `.yt-mirror` subfolder of a channel folder with metadata, thumbnails and temp files | `HIDDEN_DIR` |
| **Adopt** | Link existing files in a folder to a channel's videos | `adoption` |
| **Keep as is / Fix in place / Re-download** | The three adopt actions (R-AD-05) | `AdoptAction` |
| **Repair metadata** | Rewrite metadata, thumbnail and subtitles into an existing file | job kind `repair_metadata` |
| **Repair dates** | Set file dates back to the published time | `repair_dates` |
| **Queue** | The ordered list of jobs | `queue` |
| **Job** | One unit of work on one video. Has a job ID used in all logs | `Job` |
| **Quality** | The target video height, or "Best available" | `Quality` |
| **Disk space guard** | Pauses the queue when free space is below a threshold | `disk_guard` |
| **Tool** | An external program the app manages: yt-dlp, ffmpeg, Deno, Python | `toolchain` |
| **Activity log** | The user-facing history of what the app did | `activity` |
| **Debug log** | Structured logs for developers and agents | `data/logs` |
| **Debug report** | The exported bundle for bug reports | `diagnostics` |
| **Banner** | A persistent message at the top of the window about an app-wide condition | `Banner` |
| **Toast** | A short confirmation that disappears | `Toast` |
| **Install kind** | How this copy was installed: `clone` or `archive` | `install_kind` |
| **App bundle** | The macOS application folder (`yt-mirror.app`) built locally on the user's Mac, which gives the running app its name and icon (R-NA-02) | `yt-mirror.app` |
| **Menu bar** | The macOS menu bar of the app with its menus and shortcuts (R-NA-03) | `menus` |
| **Theme center** | The one folder that holds every visual value: tokens, Tailwind preset, fonts, brand icon (R-TH-01) | `frontend/src/design/` |
| **Token** | A named visual value, stored as a CSS variable and named after its purpose (R-TH-02, R-TH-03) | `--ytm-*` |
| **Theme** | One block of token values, for example light or dark (R-TH-04) | `data-theme` |

Words to avoid: "sync" as a verb for downloading (use "mirror"), "downloaded" as a status (use "synced"), "deleted" for videos gone from YouTube (use "removed from YouTube"), "blacklist" or "ignore" (use "exclude"), "import" for existing files (use "adopt").

# yt-mirror V1: Open Questions and Things to Verify

Everything here must be resolved before or during the milestone named. When an item is resolved, move the answer into the right document, add a decision record if it was a real choice, and delete the item.

## To verify by experiment (assumptions made during planning)

| ID | Assumption | How to verify | Needed by |
|---|---|---|---|
| Q-01 | Minimum macOS version | Find the oldest macOS on which uv-managed Python, pywebview, Deno and the chosen ffmpeg build all run. State it in README and website | M0 |
| Q-02 | The creation date of a file can be set from Python with `setattrlist` (`ATTR_CMN_CRTIME`), and Finder shows it | Write the adapter and an integration test on a macOS runner. Check APFS, and exFAT for external drives. Fallback: set the modification time earlier than the creation time and confirm the creation time follows | M3 |
| Q-03 | A launcher app bundle created locally by the installer, and files fetched with `curl`, are not blocked by Gatekeeper | Test the installer on a clean Mac, on the two newest macOS versions | M9 |
| Q-04 | yt-dlp option names and behaviour in [ARCHITECTURE.md](ARCHITECTURE.md) section 7.3: format selectors, subtitle options, embedding order, attaching the info JSON to MKV, passing the Deno path, cancelling from a progress hook | Check against the pinned yt-dlp version and write gateway tests with recorded data | M3 |
| Q-05 | A trustworthy source of static ffmpeg and ffprobe builds for macOS arm64 and x86_64, with a license that allows downloading them at first run | Compare the available sources. Pin versions and checksums in the tool manifest. Record the choice as a decision | M1 |
| Q-06 | The channel feed returns exact published times for the newest videos (believed to be about 15 entries) and is stable enough to rely on | Fetch feeds for several channels and compare with full metadata | M4 |
| Q-07 | macOS notifications can be sent from an unsigned Python process started by a local launcher | Try the candidate mechanisms. If none works without signing, notifications fall back to in-app toasts only and R-FB-06 is moved to a later version | M7 |
| Q-08 | Slow-path exact date fetching at one request per 2 seconds does not trigger YouTube rate limits for typical channels | Measure on a 1,000-video channel. Adjust the rate and the estimate shown in the UI | M4 |
| Q-09 | pywebview on macOS supports what the UI needs: native folder picker, opening external links in the default browser, window minimum size, a close handler that can ask for confirmation | Prototype in M0 | M0 |
| Q-10 | The mockups in `docs/design/v1/` render as intended | Visual review of every screen. Fix the canvas and regenerate the export | Before M5 |
| Q-11 | The Google Cloud Console steps in the API key guide match the current console | Follow them once and correct the wording | M4 |
| Q-12 | Approximate dates from the flat channel listing are available for all videos | Check the listing output for old and new videos. If missing, show "date pending" instead of an approximate date | M2 |

Facts already verified during planning (November 2026):
- yt-dlp needs an external JavaScript runtime for full YouTube support since release 2025.11.12, and recommends Deno.
- yt-dlp stopped setting file modification times by default in release 2025.07.21, so yt-mirror must set dates itself.
- The YouTube Data API `videos.list` accepts up to 50 IDs per request and costs 1 quota unit. The default quota is 10,000 units per day.

## Decisions the maintainer still has to make

| ID | Question | Default if not decided |
|---|---|---|
| Q-20 | GitHub owner and repository name (needed for the installer URL, website URL, issue links) | Placeholder `<owner>/yt-mirror` |
| Q-21 | Copyright holder name in `LICENSE` | "yt-mirror contributors" |
| Q-22 | Contact for the code of conduct and for security reports | GitHub private vulnerability reporting, no email |
| Q-23 | Should the app check for updates on first run before the user has seen the setting? | Yes, it is one request to GitHub with no personal data |
| Q-24 | Does excluding by rule apply to videos that are already downloaded? | Yes, following the "exclude a downloaded video" setting |

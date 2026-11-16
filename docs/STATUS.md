# yt-mirror: Status

This file is the single source of truth for where the project stands. Read it at the start of every session. It is updated only inside milestone pull requests, so `main` always shows what has really been merged.

**Version in progress:** 1.0
**Next milestone to start:** M4

| Milestone | Title | Status | Branch | Pull request | Merged |
|---|---|---|---|---|---|
| M0 | Project skeleton and tooling | Done | `m0-project-skeleton` | [#1](https://github.com/mderis/yt-mirror/pull/1) | 2026-11-13 |
| M1 | Toolchain and app identity | Done | `m1-toolchain-and-app-identity` | [#2](https://github.com/mderis/yt-mirror/pull/2) | 2026-11-14 |
| M2 | Channels and catalogue | Done | `m2-channels-and-catalogue` | [#3](https://github.com/mderis/yt-mirror/pull/3) | 2026-11-14 |
| M3 | Downloading one video correctly | Done | `m3-download-one-video` | [#4](https://github.com/mderis/yt-mirror/pull/4) | 2026-11-16 |
| M4 | Exact dates and automatic checks | In progress | `m4-exact-dates-and-checks` | [#5](https://github.com/mderis/yt-mirror/pull/5) | |
| M5 | Queue | Not started | | | |
| M6 | Excluding | Not started | | | |
| M7 | Settings, feedback, activity, help | Not started | | | |
| M8 | Adopting existing files | Not started | | | |
| M9 | Installer, updater, uninstall, release pipeline | Not started | | | |
| M10 | Website and documentation | Not started | | | |
| M11 | Hardening and release | Not started | | | |

Status values: `Not started`, `In progress` (branch and draft pull request), `In review` (pull request marked ready for review), `Done` (merged).

## Notes carried between sessions

Short facts the next session needs and cannot get from the code or the other docs: an open question that was answered, something that was deliberately postponed, a known problem. Newest first. Remove a note when it no longer matters.

- **M4 owes the rename of a file named by its video ID (R-FN-01, R-FN-06).** A title with nothing storable gives `<video id>.mkv`. When the title later changes to one that leaves something, the rename of R-FN-06 gives the file its title. The maintainer asked for a test of exactly that case.
- **The real Trash of macOS has not run in a test (M3).** Every test and every end-to-end app uses a folder of its own as the Trash (`YTM_TRASH_DIR`), so no test fills the Trash of the person who runs it. On the manual checklist: remove a channel with "Delete the files", see the files in the Trash, and "Put Back" one.
- **M8 must tag adopted files with their video ID (R-CH-32).** From M3, "Delete the files" moves a video file to the Trash only when the video ID inside it matches. A downloaded file carries it; an adopted file must get it in M8 (when its metadata is repaired), or a removal keeps it in the folder.
- **M8 reads `.yt-mirror/channel.json` (R-FI-05).** From M3 every channel folder lists its channels there (ID, handle, title), and a shared folder lists each of them. Reading it, to adopt a folder or to recover a lost database, belongs to the adoption of existing files: in a shared folder, each video file is matched to its channel by the video ID inside the file, not by the folder. One channel folder can lie inside another (for example a custom folder that is the library): each keeps its own channel file, and removing one never touches the other's files (tested).
- **M5 owes one item of the first review of M3 (L2).** A removal and a quit wait a fixed time for a running download (30 s and 2 s). Since the second review, Cancel stops the job's ffmpeg, a removal that waits in vain changes nothing (`CHANNEL_BUSY`), and a quit's left-overs are cleaned up at the next start; M5, with several workers, should make the wait visible. L3 was fixed in M3 after the second review: a marker stays until its folder can be reached, and every start sweeps the temp folders of jobs that ended.
- **A backup of the database before an upgrade belongs to M9 (R-UP-02, R-UP-03).** Until then a migration runs in one transaction that also covers changes of tables (D-081): a migration that fails changes nothing (tested). No file backup is taken today.
- **The progress of a download comes from the real yt-dlp in an order the fakes now copy (M3).** Steps before the download (the tags, the thumbnail) and the subtitle file come first; only steps after the first byte of a stream are processing, and the two streams count together for one percent. A media test downloads a real MKV with the real yt-dlp from a server on this Mac; the order of YouTube itself was seen with a live download on 16 November 2026.
- **M5 changes what a quit does to a download (D-080).** In M3 a quit, a crash or a cancel deletes the temp folder of the job and the video is "not downloaded" again. R-QU-05 (resume from the partial file) and R-QU-06 (queued again at start) replace this in M5, and keep a partial file in the hidden `tmp/` folder.
- **First task after M3 is merged: start "Update screenshots" once on `main`** (`gh workflow run update-screenshots.yml --ref main`) and confirm that it makes the same images as the last CI run of the M3 pull request: the summary of the run must show 0 differing pixels, or only text noise under the limit, for all 138 images. Until it is on `main`, GitHub cannot start it.
- **M5's checkbox and the arrow of the Quality select are drawn from tokens (DESIGN.md section 4, "Form controls").** The select still shows each browser's own arrow (decided 2026-11-16: in M5, with the checkbox). Both follow the radio group of M3: a real `<input type="checkbox">` with `appearance: none`, every state, the focus ring on `:focus`, "Increase contrast" and "Reduce motion", each covered by tests in the real browsers as `e2e/tests/radio.spec.ts` does.
- **M3 runs one download at a time.** The downloader takes jobs under a lock and keeps everything by job ID, so M5 only raises the number of workers (R-QU-01). There is no setting for it yet.
- **In M5, an abandoned request must not hold up the queue.** In M3 a cancel during the metadata lookup ends the job at once, but the one worker still waits for that lookup to answer (3 to 10 s with real YouTube) before it takes the next job (accepted for M3, 2026-11-16). With the parallel workers of M5 (R-QU-01), the next job starts at once on a free worker, and the abandoned request counts against no limit. The e2e test "R-QU-02: a cancel while YouTube is only asked ends within half a second, and Mirror works again" in `e2e/tests/downloads.spec.ts` then allows less than 20 s for the next download.
- **R-MI-01 is partly done (M3).** Mirror works for one video, from its row and from the details panel, and several presses queue several jobs. Selecting several rows and the bulk bar arrive in M5. No test names R-MI-01 for selection.
- **The settings of downloads are stored with their defaults (M3), without controls.** Default quality (Best available), English subtitles and the auto-generated fallback (on), the thumbnail next to the video (off). Their controls come with the settings screen of M7.
- **Q-27 moved to M4.** No channel with a scheduled premiere or a members-only video was found in M3. The fixture channel `premieres` stands in for both until then.
- **Not checked by a person yet (M3).** On the manual checklist (TESTING section 8): a downloaded file plays in IINA with its chapters, subtitles and cover; Finder sorts by Date Created in the order of the channel; Get Info shows the published time. The live test downloaded a real video and checked the file and its dates by program.
- **`YTM_TRASH_DIR` (M3).** Tests and the end-to-end apps give the app a folder of its own as the Trash, so that "Delete the files" never fills the Trash of the person who runs them. No test may use the real Trash.
- **The help of M7 recommends IINA for playing the MKV files (R-UI-10).** "Play" keeps opening the user's default player. The help says why: IINA is free and plays MKV with its chapters and subtitles.
- **Hand tests that delete a tool are done on a copy of the app folder (TESTING rule 9).** In the review of M2, `rm -r tools/deno tools/ffmpeg` followed by `./start` was run again from the shell history of M1, so the tools were downloaded again at two starts. No code was at fault. The backend test session and the smoke test now fail when the tools of the app folder change.
- **The design of the exact date fetch for M4 is a proposal in OPEN-QUESTIONS,** with the measurements with and without the free API key. With the key, 6,599 videos got their exact dates in 132 requests and 153 seconds. Decide it in the plan of M4.
- **`YTM_YOUTUBE_API_KEY` is read by nothing but the log redactor (M2).** Live tests and probes take a key from it. It is never written to a file, a fixture or a commit.
- **A paused channel with new videos says "N new videos", not "Paused" (R-FB-01).** New outranks paused for 14 days. The menu of the channel says "Resume channel". Raised with the maintainer in the review of M2.
- **The yt-dlp update of M9 must update `yt-dlp-ejs` with it (D-078).** The JavaScript challenge solver is the package `yt-dlp-ejs`, in the version yt-dlp pins. A yt-dlp without its matching solver offers fewer formats.
- **A metadata lookup of one video takes 3.5 to 10 seconds from the maintainer's network (M2, for M4).** The numbers and what follows from them are in OPEN-QUESTIONS (Q-08). From the CI runners of GitHub every such lookup was refused with the "not a bot" check, so nothing that looks up a video can be tested live in CI.
- **YouTube is reachable from the maintainer's Mac only on and off.** Requests sometimes stall completely for a while. The gateway has its own time limits. Live tests can fail for this reason alone: run them again before believing a failure.
- **The video list is not virtual before M5.** A channel of 5,000 videos takes about two seconds to draw in WebKit, once per load of its catalogue. The list is built so that nothing else draws it again (D-073).
- **"What to mirror" of a channel is only stored (M2).** It takes effect in M5 (auto-mirror). The quality of a channel applies to downloads from M3. The date of "only videos uploaded after" is stored as the start of that day in the time zone of the Mac.
- **The Chromium screenshots come from CI.** After an intended visual change, run WebKit locally, push, and take the new Chromium images from the `e2e-results` artifact of the failed run.
- **The native Mac app relies on the pinned pywebview (M1).** How it works: ARCHITECTURE section 7.10 and decisions D-048 to D-052. pywebview stays pinned exactly. The tests with a real window (`backend/tests/integration/app/test_window_app.py`) are the guard for an update. The menu bar of M5 is built through the same adapter (`adapters/native_app_mac.py`), with public calls of pywebview and AppKit only.
- **M5 builds the quit confirmation on the quit path of M1 (D-052).** M1 built only the shutdown work: nothing in the app listens to the `closing` event, and no quit is ever held. What exists when: the table in ARCHITECTURE section 7.10. The decision part, to be built in M5, hangs on the `closing` event of the pywebview window, which also fires for Cmd+Q, the Dock and a logout. A logout, a restart and a shutdown must never be held for a question: the quit request of macOS carries its reason. The experiment code for all of this is not in the repository: the decision record describes it.
- **M7 owes the activity entry of an installed tool (R-IN-03, D-057).** It names the source the tool came from. Until the activity log exists, the source is in the debug log, in `./start --doctor` and in `/api/tools`: the maintainer accepted this in the review of M1.
- **M9 must ship the icon source file and the token file in the release archive (D-056),** or the installer cannot build the app bundle. The installer builds the bundle with `app/bundle.py`, with the identity of an installed copy ("yt-mirror").
- **Not checked by a person yet (M1).** The manual checklist of TESTING section 8 has four new items: the name and icon in the Dock, the app switcher and Activity Monitor, a real click on the Dock icon, the Edit shortcuts typed by hand, and a real logout, restart and shutdown on the maintainer's Mac. Automated tests and the experiment of Q-24 cover the mechanisms behind each of them.
- **Two tests need an unlocked screen.** The two tests that check that the window comes to the front skip themselves while the screen of the Mac is locked. CI runs them.
- **The first ffmpeg source builds no new Intel releases from January 2027 (D-053).** Intel stays at the pinned version.
- **Do not start M7 without the About window mockup.** The maintainer supplies it before M7 (R-NA-05, DESIGN section 7.2). If `docs/design/v1/` has no About mockup when an M7 session starts, stop and ask for it.
- **Labelling tests (TESTING rule 1, D-046).** A test whose behaviour no requirement states is a spec gap: propose the requirement to the maintainer, do not mark the test `infra` and do not borrow an ID.
- **Q-09 is still not checked by a person.** The folder dialog is built on what the window library documents, and tested with a stand-in window. Nobody has clicked a folder in the real dialog yet. It is on the manual checklist (TESTING section 8).
- **Stubs that later milestones replace:** `./start --update` only says it is not available (M9). `./start --doctor` checks what exists so far, the tools included, not the network (M7). The fake YouTube has every channel of TESTING section 4.
- **The requirements coverage script only reports.** CI switches to `--strict` in M11.
- **TypeScript is 5.9 on purpose** (D-039). Move to a newer one when `openapi-typescript` and `typescript-eslint` support it.
- **Playwright's own Chromium cannot be downloaded on the maintainer's Mac** (the download server refuses the location). There, local runs use the installed Chrome with `YTM_E2E_CHROME_CHANNEL=chrome`, and Playwright's own Chromium runs only in CI. WebKit runs locally and in CI. See TESTING section 6.
- **Pre-commit hooks are turned on in the maintainer's clone** (`.git/hooks/pre-commit`). Turn them off with `scripts/uv run pre-commit uninstall`.

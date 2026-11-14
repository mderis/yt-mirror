/**
 * Every user-visible text of the app, in English (R-PL-06).
 *
 * Components never contain text. They refer to a key in this file. Use the
 * words of docs/GLOSSARY.md.
 */
export const en = {
  app: {
    name: 'yt-mirror',
  },
  /**
   * The user text of each error code (R-ER-01, R-ER-02), by the text key of the code:
   * what happened, what yt-mirror is doing about it, what the user can do.
   * Milestone M7 adds the texts of the remaining codes.
   */
  errors: {
    local_server_unreachable: {
      happened: 'The window cannot reach yt-mirror.',
      doing: 'yt-mirror does not try again by itself here.',
      action: 'Try again. If that does not help, quit yt-mirror and start it again.',
    },
    network_unreachable: {
      happened: 'A download could not be reached.',
      doing: 'yt-mirror tried every source it knows and installed nothing.',
      action: 'Check your internet connection, then try again.',
    },
    checksum_mismatch: {
      happened: 'A downloaded file was not the file yt-mirror expected.',
      doing: 'yt-mirror threw the file away and did not use it.',
      action: 'Try again. If it happens again, report a problem.',
    },
    disk_full: {
      happened: 'There is no room left on the disk.',
      doing: 'yt-mirror installed nothing.',
      action: 'Free some space, then try again.',
    },
    tool_missing: {
      happened: 'A tool that yt-mirror needs is missing or does not work.',
      doing: 'yt-mirror can download it again.',
      action: 'Choose "Install now".',
    },
  },
  /** The first-run screen (R-IN-03, design: Setup.html). */
  setup: {
    title: 'Getting yt-mirror ready',
    intro:
      'yt-mirror needs a few tools. They are downloaded into the app folder, so nothing is installed or changed anywhere else on your Mac.',
    tools: {
      python: { name: 'Python environment', about: 'Installed in the app folder' },
      ytdlp: { name: 'yt-dlp', about: 'The YouTube download engine' },
      ffmpeg: {
        name: 'ffmpeg',
        about: 'Merges video and audio, embeds metadata and subtitles',
      },
      deno: { name: 'Deno', about: 'Needed by yt-dlp to read YouTube pages' },
    },
    installed: 'Installed',
    waiting: 'Waiting',
    downloading: 'Downloading {percent}%',
    downloadingUnknown: 'Downloading',
    progressLabel: 'Progress of {tool}',
    failed: 'Download failed: {reason}',
    /** The short reason of a failed installation, by the text key of its error code. */
    failure: {
      network_unreachable: 'no internet connection',
      checksum_mismatch: 'the downloaded file was damaged',
      disk_full: 'the disk is full',
      tool_missing: 'the tool does not work on this Mac',
      internal: 'an unexpected problem',
    },
    cannotInstall: 'Missing. Quit yt-mirror and open it again to repair it.',
    retry: 'Try again',
    size: 'About 120 MB in total. This only happens once.',
    continue: 'Continue',
  },
  /** The banner of a tool that is missing or broken after the first run (R-IN-04). */
  toolBanner: {
    missing: '{tool} is missing. yt-mirror cannot mirror videos without it.',
    broken: '{tool} no longer works. yt-mirror cannot mirror videos without it.',
    cannotInstall: '{tool} is missing. Quit yt-mirror and open it again to repair it.',
    installing: 'Installing {tool}',
    failed: '{tool} could not be installed: {reason}.',
    install: 'Install now',
  },
  placeholder: {
    running: 'yt-mirror is running.',
    version: 'Version {version}',
    connecting: 'Connecting to yt-mirror',
    failed: 'yt-mirror answered with an error.',
    errorCode: 'Error code: {code}',
    retry: 'Try again',
  },
  themePreview: {
    title: 'Theme preview',
    intro: 'Every token and every shared component, in every theme. For development only.',
    theme: 'Theme: {name}',
    sample: 'The quick brown fox jumps over the lazy dog',
    groups: {
      color: 'Colours',
      'font-size': 'Font sizes',
      'font-weight': 'Font weights',
      font: 'Font families',
      'line-height': 'Line heights',
      space: 'Spacing step',
      radius: 'Corner radii',
      shadow: 'Shadows',
      duration: 'Animation durations',
    },
    brand: 'Brand icon',
    components: 'Shared components',
    sampleButton: 'Mirror',
    sampleSecondaryButton: 'Try again',
    sampleDisabledButton: 'Continue',
    sampleProgress: 'Sample progress',
    sampleBanner: 'ffmpeg is missing. yt-mirror cannot mirror videos without it.',
    sampleErrorBanner: 'Deno could not be installed: no internet connection.',
    sampleBannerAction: 'Install now',
    reducedMotion: 'With reduced motion: {value}',
    hoverMe: 'Hover to see the duration',
    spaceSteps: 'Multiples: 1, 2, 4, 8',
    sampleGhostButton: 'Cancel',
    sampleDangerButton: 'Remove channel',
    sampleInfoBanner: 'This channel was added before. Here it is.',
    sampleIconButton: 'More actions',
    sampleChips: {
      plain: 'Not downloaded',
      neutral: 'Queued',
      progress: 'Downloading 42%',
      ok: 'Synced · 1080p',
      failed: 'Failed',
    },
    sampleBadge: '3 new',
    sampleTag: 'New',
    sampleField: "Channel link or {'@'}handle",
    sampleFieldHint: 'Regular videos are mirrored. Shorts and live streams are skipped.',
    sampleFieldError: 'This is a video, not a channel.',
    samplePlaceholder: "https://www.youtube.com/{'@'}channel",
    sampleSelect: 'Quality',
    sampleSelectOptions: { best: 'Use default (Best available)', p1080: '1080p' },
    sampleRadio: 'What to mirror',
    sampleRadioOptions: {
      pick: 'Let me pick videos myself',
      pickHint: 'Nothing downloads until you select videos.',
      all: 'Mirror everything and keep it in sync (auto-mirror)',
    },
    sampleMenu: 'Channel actions',
    sampleMenuItems: { check: 'Check now', open: 'Open on YouTube', remove: 'Remove channel' },
    sampleDialog: 'Remove Sample Channel One?',
    sampleDialogBody:
      'The channel disappears from yt-mirror, including its exclude list and settings.',
    sampleDialogClose: 'Close',
    sampleEmpty: 'No videos yet',
    sampleEmptyText: 'This channel has no regular videos. Shorts and live streams are not listed.',
    sampleChannel: 'Sample Channel One',
    sampleChannelStatus: 'Up to date · checked 2 min ago',
    sampleChannelChecking: 'Checking for new videos...',
    sampleVideo: 'Building a cabin in the woods, part 12',
    sampleDuration: '24:18',
    sampleViews: '48K views',
    sampleUploaded: 'Uploaded',
    sampleExactDate: '11 Nov 2026',
    sampleAroundDate: 'around 2005',
    sampleDateNote: 'Exact date pending',
  },
} as const

export type Messages = typeof en

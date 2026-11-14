/**
 * Every user-visible text of the app, in English (R-PL-06).
 *
 * Components never contain text. They refer to a key in this file. Use the
 * words of docs/GLOSSARY.md.
 */
export const en = {
  app: {
    name: 'yt-mirror',
    /** Stands between facts in one line: "248 videos · 212 synced". */
    separator: '·',
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
      happened: 'yt-mirror could not reach the internet.',
      doing: 'Nothing was changed.',
      action: 'Check your internet connection, then try again.',
    },
    rate_limited: {
      happened: 'YouTube asked yt-mirror to slow down.',
      doing: 'Nothing was changed.',
      action: 'Wait a few minutes, then try again.',
    },
    bot_check: {
      happened: 'YouTube asks to confirm that you are not a bot.',
      doing: 'yt-mirror pauses what it asks of YouTube by itself and tries again later.',
      action: 'Wait, or try another network or another VPN location.',
    },
    youtube_changed: {
      happened: 'YouTube answered in a way that yt-mirror does not understand.',
      doing: 'Nothing was changed.',
      action: 'Try again later. If it keeps happening, yt-mirror needs an update.',
    },
    channel_not_found: {
      happened: 'YouTube has no channel with this address.',
      doing: 'Nothing was changed.',
      action: 'Check the link or the handle, then try again.',
    },
    invalid_channel_input: {
      happened: 'This is not a channel.',
      doing: 'Nothing was changed.',
      action: "Paste a channel link, a handle such as {'@'}name, or a channel ID.",
    },
    folder_unavailable: {
      happened: 'The folder cannot be used.',
      doing: 'Nothing was changed.',
      action: 'Check that its drive is connected, or choose another folder.',
    },
    permission_denied: {
      happened: 'macOS does not let yt-mirror use this folder.',
      doing: 'Nothing was changed.',
      action: 'Choose another folder, or allow yt-mirror to use it in System Settings.',
    },
    internal: {
      happened: 'Something unexpected went wrong inside yt-mirror.',
      doing: 'Nothing was changed.',
      action: 'Try again. If it happens again, quit yt-mirror and start it again.',
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
  /** An error whose code has no texts of its own yet, and what goes with every error. */
  error: {
    unknown: 'yt-mirror answered with an error.',
    code: 'Error code: {code}',
    dismiss: 'Dismiss',
  },
  /** The page before the window is connected to its backend (R-ER-04). */
  connection: {
    connecting: 'Connecting to yt-mirror',
    retry: 'Try again',
  },
  /** How long ago a check was. Dates of videos are never written like this (R-DT-02). */
  time: {
    justNow: 'just now',
    minutesAgo: '{count} min ago',
    hoursAgo: '{count} h ago',
    daysAgo: 'yesterday | {count} days ago',
    onDate: 'on {date}',
  },
  /** The shell: the sidebar and what belongs to the whole window (R-UI-01). */
  shell: {
    channels: 'Channels',
    checkAll: 'Check all channels now',
    addChannel: 'Add channel',
    freeSpace: '{size} free on {disk}',
  },
  /** The one status line of a channel (R-FB-01, design: States.html). */
  channelStatus: {
    checking: 'Checking for new videos...',
    upToDate: 'Up to date · checked {ago}',
    newVideos: '{count} new video | {count} new videos',
    paused: 'Paused',
    couldNotCheck: 'Could not check',
    newBadge: '{count} new',
  },
  /** The welcome screen of an app without channels (R-UI-02, design: Welcome.html). */
  welcome: {
    title: 'Mirror your first channel',
    intro:
      "Paste a YouTube channel link or {'@'}handle. yt-mirror lists every video and keeps a folder on your disk in sync with it.",
    field: 'Channel link or handle',
    placeholder: "https://www.youtube.com/{'@'}channel",
    add: 'Add channel',
    points: {
      pick: 'Pick videos or mirror everything',
      exclude: 'Exclude videos forever',
      names: 'Files named exactly like the titles',
    },
    savedIn: 'Videos will be saved in {folder}.',
  },
  /** The add channel dialog (R-CH-01 to R-CH-06, design: AddChannel1.html, AddChannel2.html). */
  addChannel: {
    title: 'Add a channel',
    close: 'Close',
    field: "Channel link or {'@'}handle",
    hint: 'Regular videos are mirrored. Shorts and live streams are skipped in this version.',
    lookingUp: 'Looking up the channel...',
    cancel: 'Cancel',
    continue: 'Continue',
    back: 'Back',
    add: 'Add channel',
    found: 'Found',
    videoCount: '{count} video | {count} videos',
    saveTo: 'Save to',
    choose: 'Choose...',
    folderHint: 'Default: a folder named after the channel inside your library.',
    existingFiles:
      'This folder already contains {count} video file. | This folder already contains {count} video files.',
    quality: 'Quality',
    qualities: {
      default: 'Use default (Best available)',
      best: 'Best available',
      '2160': '2160p (4K)',
      '1440': '1440p',
      '1080': '1080p',
      '720': '720p',
      '480': '480p',
    },
    mirror: 'What to mirror',
    pick: 'Let me pick videos myself',
    pickHint: 'Nothing downloads until you select videos.',
    all: 'Mirror everything and keep it in sync (auto-mirror)',
    allHint: 'All {count} videos now, and new ones as they appear.',
    allHintWithoutCount: 'All videos now, and new ones as they appear.',
    after: 'Auto-mirror, but only videos uploaded after a date',
    afterDate: 'Uploaded after',
    /** Why the pasted text is no channel, and what is accepted (R-CH-02). */
    rejected: {
      empty: "Paste a channel link, a handle such as {'@'}name, or a channel ID.",
      video:
        "This is a video, not a channel. Paste the link of its channel, a handle such as {'@'}name, or a channel ID.",
      playlist:
        "This is a playlist, not a channel. Paste the link of the channel, a handle such as {'@'}name, or a channel ID.",
      other:
        "This is not a channel. Paste a channel link, a handle such as {'@'}name, or a channel ID.",
    },
    existing: '{channel} was added before. Here it is.',
  },
  /** The page of a channel (R-CH-10 to R-CH-35, design: Main.html and the State mockups). */
  channel: {
    videos: '{count} video | {count} videos',
    synced: '{count} synced',
    excluded: '{count} excluded',
    checked: 'Checked {ago}',
    checkedWithNew: 'Checked {ago}, {count} new video | Checked {ago}, {count} new videos',
    fullCheck: 'Full check {ago}',
    checking: 'Checking for new videos...',
    lastCheckFailed: 'Last check failed',
    paused: 'Paused. No checks until you resume.',
    checkNow: 'Check now',
    openFolder: 'Open folder',
    moreActions: 'More actions',
    menu: {
      label: 'Actions of {channel}',
      check: 'Check now',
      fullCheck: 'Full check',
      pause: 'Pause channel',
      resume: 'Resume channel',
      openFolder: 'Open folder',
      openOnYouTube: 'Open on YouTube',
      remove: 'Remove channel',
    },
    listing: {
      found:
        'Reading the video list from YouTube: {count} video found so far... | Reading the video list from YouTube: {count} videos found so far...',
      starting: 'Reading the video list from YouTube...',
      progress: 'Progress of the video list',
      hint: 'Large channels can take a minute. You can keep using the app.',
    },
    fullCheckProgress: 'Full check: {done} of about {total}',
    fullCheckProgressWithoutTotal: 'Full check: {done}',
    fullCheckLabel: 'Progress of the full check',
    cancelCheck: 'Cancel',
    failed: {
      reach: 'Could not reach YouTube',
      keptList:
        'The video list below is from the last successful check ({when}). Your downloaded files are not affected.',
      noList: 'The video list could not be read yet.',
      tryAgain: 'Try again',
    },
    empty: {
      title: 'No videos yet',
      text: 'This channel has no regular videos. Shorts and live streams are not listed.',
    },
    list: {
      region: 'Video list',
      label: 'Videos',
      uploaded: 'Uploaded {date}',
      uploadedAround: 'Uploaded around {date}',
      datePending: 'date pending',
      dateNote: 'Exact date pending',
      views: '{count} views',
      notDownloaded: 'Not downloaded',
      removed: 'Removed from YouTube',
      newTag: 'New',
      failed: 'The video list could not be loaded.',
      retry: 'Try again',
    },
  },
  /** The remove channel dialog (R-CH-32, design: RemoveChannel.html). */
  removeChannel: {
    title: 'Remove {channel}?',
    body: 'The channel disappears from yt-mirror, including its exclude list and settings.',
    folder: 'Its folder and everything in it stay where they are: {folder}',
    cancel: 'Cancel',
    remove: 'Remove channel',
    close: 'Close',
  },
  /** The banner of the "not a bot" check of YouTube (R-ER-05, R-FB-04). */
  youtubePause: {
    title: 'YouTube asks to confirm that you are not a bot',
    text: 'YouTube does this for some network addresses, whatever the channel or the video. yt-mirror has stopped asking YouTube by itself and tries again at {time}. You can wait, or try another network or another VPN location.',
    tryNow: 'Try now',
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

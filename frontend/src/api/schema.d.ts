/**
 * Generated from the OpenAPI schema of the backend. Do not edit by hand.
 * Regenerate with: npm --prefix frontend run gen:api
 */

export interface paths {
  '/api/channels': {
    parameters: {
      query?: never
      header?: never
      path?: never
      cookie?: never
    }
    get?: never
    put?: never
    /**
     * Add Channel
     * @description Add a channel that was looked up, and start its first listing (R-CH-05).
     */
    post: operations['addChannel']
    delete?: never
    options?: never
    head?: never
    patch?: never
    trace?: never
  }
  '/api/channels/check-all': {
    parameters: {
      query?: never
      header?: never
      path?: never
      cookie?: never
    }
    get?: never
    put?: never
    /**
     * Check All Channels
     * @description Start a quick check of every channel that is not paused (R-CH-23).
     */
    post: operations['checkAllChannels']
    delete?: never
    options?: never
    head?: never
    patch?: never
    trace?: never
  }
  '/api/channels/lookup': {
    parameters: {
      query?: never
      header?: never
      path?: never
      cookie?: never
    }
    get?: never
    put?: never
    /**
     * Look Up Channel
     * @description Resolve what the user pasted to the preview of a channel (R-CH-03).
     */
    post: operations['lookUpChannel']
    delete?: never
    options?: never
    head?: never
    patch?: never
    trace?: never
  }
  '/api/channels/lookup/{channel_id}/avatar': {
    parameters: {
      query?: never
      header?: never
      path?: never
      cookie?: never
    }
    /**
     * Get Preview Avatar
     * @description Return the avatar of a channel that was looked up, for its preview.
     */
    get: operations['getPreviewAvatar']
    put?: never
    post?: never
    delete?: never
    options?: never
    head?: never
    patch?: never
    trace?: never
  }
  '/api/channels/lookup/{channel_id}/video-count': {
    parameters: {
      query?: never
      header?: never
      path?: never
      cookie?: never
    }
    /**
     * Get Video Count
     * @description Return the video count of a preview, or none when YouTube gave none in time.
     */
    get: operations['getPreviewVideoCount']
    put?: never
    post?: never
    delete?: never
    options?: never
    head?: never
    patch?: never
    trace?: never
  }
  '/api/channels/{channel_id}': {
    parameters: {
      query?: never
      header?: never
      path?: never
      cookie?: never
    }
    /**
     * Get Channel
     * @description Return one channel as the interface shows it.
     */
    get: operations['getChannel']
    put?: never
    post?: never
    /**
     * Remove Channel
     * @description Remove a channel with its catalogue, and its files or not (R-CH-32).
     *
     *     The answer lists every file that stayed, with its reason.
     */
    delete: operations['removeChannel']
    options?: never
    head?: never
    /**
     * Change Channel
     * @description Pause or resume a channel (R-CH-31).
     */
    patch: operations['changeChannel']
    trace?: never
  }
  '/api/channels/{channel_id}/auto-mirror': {
    parameters: {
      query?: never
      header?: never
      path?: never
      cookie?: never
    }
    get?: never
    /**
     * Set Auto Mirror
     * @description Turn auto-mirror of a channel on or off (R-MI-02). On asks before a large start.
     */
    put: operations['setAutoMirror']
    post?: never
    delete?: never
    options?: never
    head?: never
    patch?: never
    trace?: never
  }
  '/api/channels/{channel_id}/auto-mirror/answer': {
    parameters: {
      query?: never
      header?: never
      path?: never
      cookie?: never
    }
    get?: never
    put?: never
    /**
     * Answer Auto Mirror
     * @description Answer the question before a large start of auto-mirror (D-095).
     */
    post: operations['answerAutoMirror']
    delete?: never
    options?: never
    head?: never
    patch?: never
    trace?: never
  }
  '/api/channels/{channel_id}/avatar': {
    parameters: {
      query?: never
      header?: never
      path?: never
      cookie?: never
    }
    /**
     * Get Avatar
     * @description Return the cached avatar of a channel (R-CH-16).
     */
    get: operations['getChannelAvatar']
    put?: never
    post?: never
    delete?: never
    options?: never
    head?: never
    patch?: never
    trace?: never
  }
  '/api/channels/{channel_id}/check': {
    parameters: {
      query?: never
      header?: never
      path?: never
      cookie?: never
    }
    get?: never
    put?: never
    /**
     * Check Channel
     * @description Start a quick or a full check of a channel (R-CH-23).
     */
    post: operations['checkChannel']
    delete?: never
    options?: never
    head?: never
    patch?: never
    trace?: never
  }
  '/api/channels/{channel_id}/check/cancel': {
    parameters: {
      query?: never
      header?: never
      path?: never
      cookie?: never
    }
    get?: never
    put?: never
    /**
     * Cancel Check
     * @description Cancel the full check of a channel that waits or runs (R-CH-27).
     */
    post: operations['cancelCheck']
    delete?: never
    options?: never
    head?: never
    patch?: never
    trace?: never
  }
  '/api/channels/{channel_id}/files-to-trash': {
    parameters: {
      query?: never
      header?: never
      path?: never
      cookie?: never
    }
    /**
     * Files To Trash
     * @description Say how many files and how much room "Delete the files" moves to the Trash (R-CH-32).
     */
    get: operations['getFilesToTrash']
    put?: never
    post?: never
    delete?: never
    options?: never
    head?: never
    patch?: never
    trace?: never
  }
  '/api/channels/{channel_id}/mirror-missing': {
    parameters: {
      query?: never
      header?: never
      path?: never
      cookie?: never
    }
    get?: never
    put?: never
    /**
     * Mirror Missing
     * @description Queue every video of the channel without a file, once (R-MI-04).
     */
    post: operations['mirrorMissing']
    delete?: never
    options?: never
    head?: never
    patch?: never
    trace?: never
  }
  '/api/channels/{channel_id}/missing/leave': {
    parameters: {
      query?: never
      header?: never
      path?: never
      cookie?: never
    }
    get?: never
    put?: never
    /**
     * Leave Missing
     * @description Leave the missing files of the channel missing, until more are missing (D-092).
     */
    post: operations['leaveMissing']
    delete?: never
    options?: never
    head?: never
    patch?: never
    trace?: never
  }
  '/api/channels/{channel_id}/missing/mirror': {
    parameters: {
      query?: never
      header?: never
      path?: never
      cookie?: never
    }
    get?: never
    put?: never
    /**
     * Mirror Them Again
     * @description Queue the missing files of the channel again, and nothing else (R-MI-06, D-092).
     */
    post: operations['mirrorThemAgain']
    delete?: never
    options?: never
    head?: never
    patch?: never
    trace?: never
  }
  '/api/channels/{channel_id}/open-folder': {
    parameters: {
      query?: never
      header?: never
      path?: never
      cookie?: never
    }
    get?: never
    put?: never
    /**
     * Open Channel Folder
     * @description Show the folder of a channel in Finder (R-CH-30).
     */
    post: operations['openChannelFolder']
    delete?: never
    options?: never
    head?: never
    patch?: never
    trace?: never
  }
  '/api/channels/{channel_id}/repair-dates': {
    parameters: {
      query?: never
      header?: never
      path?: never
      cookie?: never
    }
    get?: never
    put?: never
    /**
     * Repair Dates
     * @description Compare the dates of a channel's synced files and repair them (R-DT-09).
     */
    post: operations['repairDates']
    delete?: never
    options?: never
    head?: never
    patch?: never
    trace?: never
  }
  '/api/channels/{channel_id}/videos': {
    parameters: {
      query?: never
      header?: never
      path?: never
      cookie?: never
    }
    /**
     * Get Channel Videos
     * @description Return the catalogue of a channel: every video, with the fields a list needs.
     */
    get: operations['getChannelVideos']
    put?: never
    post?: never
    delete?: never
    options?: never
    head?: never
    patch?: never
    trace?: never
  }
  '/api/events': {
    parameters: {
      query?: never
      header?: never
      path?: never
      cookie?: never
    }
    /**
     * Get Events
     * @description Open the event stream of this window.
     */
    get: operations['getEvents']
    put?: never
    post?: never
    delete?: never
    options?: never
    head?: never
    patch?: never
    trace?: never
  }
  '/api/folders/choose': {
    parameters: {
      query?: never
      header?: never
      path?: never
      cookie?: never
    }
    get?: never
    put?: never
    /**
     * Choose Folder
     * @description Show the folder dialog of macOS and return what the user chose (R-CH-05).
     */
    post: operations['chooseFolder']
    delete?: never
    options?: never
    head?: never
    patch?: never
    trace?: never
  }
  '/api/health': {
    parameters: {
      query?: never
      header?: never
      path?: never
      cookie?: never
    }
    /**
     * Get Health
     * @description Return the app version and the database schema version.
     */
    get: operations['getHealth']
    put?: never
    post?: never
    delete?: never
    options?: never
    head?: never
    patch?: never
    trace?: never
  }
  '/api/jobs/{job_id}/cancel': {
    parameters: {
      query?: never
      header?: never
      path?: never
      cookie?: never
    }
    get?: never
    put?: never
    /**
     * Cancel Job
     * @description Cancel a download that waits or runs (R-QU-02).
     */
    post: operations['cancelJob']
    delete?: never
    options?: never
    head?: never
    patch?: never
    trace?: never
  }
  '/api/queue': {
    parameters: {
      query?: never
      header?: never
      path?: never
      cookie?: never
    }
    /**
     * Get Queue
     * @description Return every download that runs or waits, in its order, and the failed videos.
     */
    get: operations['getQueue']
    put?: never
    post?: never
    delete?: never
    options?: never
    head?: never
    patch?: never
    trace?: never
  }
  '/api/queue/clear-waiting': {
    parameters: {
      query?: never
      header?: never
      path?: never
      cookie?: never
    }
    get?: never
    put?: never
    /**
     * Clear Waiting
     * @description Remove every download that waits from the line (R-QU-02).
     */
    post: operations['clearWaiting']
    delete?: never
    options?: never
    head?: never
    patch?: never
    trace?: never
  }
  '/api/queue/folders/{channel_id}/try-again': {
    parameters: {
      query?: never
      header?: never
      path?: never
      cookie?: never
    }
    get?: never
    put?: never
    /**
     * Try Folder Again
     * @description Look again whether the folder of a channel can be reached (R-QU-11).
     */
    post: operations['tryFolderAgain']
    delete?: never
    options?: never
    head?: never
    patch?: never
    trace?: never
  }
  '/api/queue/pause': {
    parameters: {
      query?: never
      header?: never
      path?: never
      cookie?: never
    }
    get?: never
    put?: never
    /**
     * Pause
     * @description Pause all downloads (R-QU-02).
     */
    post: operations['pauseQueue']
    delete?: never
    options?: never
    head?: never
    patch?: never
    trace?: never
  }
  '/api/queue/reorder': {
    parameters: {
      query?: never
      header?: never
      path?: never
      cookie?: never
    }
    get?: never
    put?: never
    /**
     * Reorder
     * @description Put the waiting downloads in the given order (R-QU-02).
     */
    post: operations['reorderQueue']
    delete?: never
    options?: never
    head?: never
    patch?: never
    trace?: never
  }
  '/api/queue/resume': {
    parameters: {
      query?: never
      header?: never
      path?: never
      cookie?: never
    }
    get?: never
    put?: never
    /**
     * Resume
     * @description Resume all downloads (R-QU-02).
     */
    post: operations['resumeQueue']
    delete?: never
    options?: never
    head?: never
    patch?: never
    trace?: never
  }
  '/api/queue/resume-anyway': {
    parameters: {
      query?: never
      header?: never
      path?: never
      cookie?: never
    }
    get?: never
    put?: never
    /**
     * Resume Anyway
     * @description Resume the queue that the disk space guard paused (R-QU-10).
     */
    post: operations['resumeAnyway']
    delete?: never
    options?: never
    head?: never
    patch?: never
    trace?: never
  }
  '/api/queue/speed-limit': {
    parameters: {
      query?: never
      header?: never
      path?: never
      cookie?: never
    }
    get?: never
    put?: never
    /**
     * Speed Limit
     * @description Change the limit of all downloads together (R-QU-03).
     */
    post: operations['setSpeedLimit']
    delete?: never
    options?: never
    head?: never
    patch?: never
    trace?: never
  }
  '/api/settings/api-key': {
    parameters: {
      query?: never
      header?: never
      path?: never
      cookie?: never
    }
    /**
     * Get Api Key
     * @description Return how the API key stands. Never the key itself.
     */
    get: operations['getApiKey']
    /**
     * Save Api Key
     * @description Save an API key in place of the saved one, and use it from now on (R-DT-12).
     */
    put: operations['saveApiKey']
    post?: never
    /**
     * Remove Api Key
     * @description Remove the API key: exact dates are looked up without it (R-DT-12).
     */
    delete: operations['removeApiKey']
    options?: never
    head?: never
    patch?: never
    trace?: never
  }
  '/api/settings/api-key/test': {
    parameters: {
      query?: never
      header?: never
      path?: never
      cookie?: never
    }
    get?: never
    put?: never
    /**
     * Test Api Key
     * @description Ask the YouTube API once with a key, or with the saved one (R-DT-12).
     */
    post: operations['testApiKey']
    delete?: never
    options?: never
    head?: never
    patch?: never
    trace?: never
  }
  '/api/state': {
    parameters: {
      query?: never
      header?: never
      path?: never
      cookie?: never
    }
    /**
     * Get State
     * @description Return the app as it is right now. The window asks when it connects.
     */
    get: operations['getState']
    put?: never
    post?: never
    delete?: never
    options?: never
    head?: never
    patch?: never
    trace?: never
  }
  '/api/state/open-channel': {
    parameters: {
      query?: never
      header?: never
      path?: never
      cookie?: never
    }
    get?: never
    /**
     * Set Open Channel
     * @description Remember which channel the user has open, for the next start (R-UI-02).
     */
    put: operations['setOpenChannel']
    post?: never
    delete?: never
    options?: never
    head?: never
    patch?: never
    trace?: never
  }
  '/api/state/view': {
    parameters: {
      query?: never
      header?: never
      path?: never
      cookie?: never
    }
    get?: never
    /**
     * Set View
     * @description Remember whether channels show a list or a grid, for the whole app (R-UI-03).
     */
    put: operations['setView']
    post?: never
    delete?: never
    options?: never
    head?: never
    patch?: never
    trace?: never
  }
  '/api/tools': {
    parameters: {
      query?: never
      header?: never
      path?: never
      cookie?: never
    }
    /**
     * Get Tools
     * @description Return the state of every tool, and whether the first-run screen is needed.
     */
    get: operations['getTools']
    put?: never
    post?: never
    delete?: never
    options?: never
    head?: never
    patch?: never
    trace?: never
  }
  '/api/tools/{name}/install': {
    parameters: {
      query?: never
      header?: never
      path?: never
      cookie?: never
    }
    get?: never
    put?: never
    /**
     * Install Tool
     * @description Start installing a tool in the background and return its state.
     */
    post: operations['installTool']
    delete?: never
    options?: never
    head?: never
    patch?: never
    trace?: never
  }
  '/api/ui/quit': {
    parameters: {
      query?: never
      header?: never
      path?: never
      cookie?: never
    }
    get?: never
    put?: never
    /**
     * Confirm Quit
     * @description Quit although downloads run: the user chose "Quit" in the question (R-QU-12).
     */
    post: operations['confirmQuit']
    delete?: never
    options?: never
    head?: never
    patch?: never
    trace?: never
  }
  '/api/ui/state': {
    parameters: {
      query?: never
      header?: never
      path?: never
      cookie?: never
    }
    get?: never
    /**
     * Report State
     * @description Tell the app what applies now, so the menu bar is enabled from it (R-NA-04).
     */
    put: operations['reportUiState']
    post?: never
    delete?: never
    options?: never
    head?: never
    patch?: never
    trace?: never
  }
  '/api/videos/mirror': {
    parameters: {
      query?: never
      header?: never
      path?: never
      cookie?: never
    }
    get?: never
    put?: never
    /**
     * Mirror
     * @description Put videos in line to be downloaded, in the order given (R-MI-01).
     */
    post: operations['mirrorVideos']
    delete?: never
    options?: never
    head?: never
    patch?: never
    trace?: never
  }
  '/api/videos/redownload': {
    parameters: {
      query?: never
      header?: never
      path?: never
      cookie?: never
    }
    get?: never
    put?: never
    /**
     * Redownload
     * @description Download synced videos again; each file is replaced once the new one is verified.
     */
    post: operations['redownloadVideos']
    delete?: never
    options?: never
    head?: never
    patch?: never
    trace?: never
  }
  '/api/videos/{video_id}': {
    parameters: {
      query?: never
      header?: never
      path?: never
      cookie?: never
    }
    /**
     * Get Video
     * @description Return everything the details panel shows of a video (R-UI-08).
     */
    get: operations['getVideo']
    put?: never
    post?: never
    delete?: never
    options?: never
    head?: never
    patch?: never
    trace?: never
  }
  '/api/videos/{video_id}/play': {
    parameters: {
      query?: never
      header?: never
      path?: never
      cookie?: never
    }
    get?: never
    put?: never
    /**
     * Play
     * @description Open the file of a video in the default player of macOS (R-UI-10).
     */
    post: operations['playVideo']
    delete?: never
    options?: never
    head?: never
    patch?: never
    trace?: never
  }
  '/api/videos/{video_id}/retry': {
    parameters: {
      query?: never
      header?: never
      path?: never
      cookie?: never
    }
    get?: never
    put?: never
    /**
     * Retry
     * @description Put a failed video in line again (R-QU-08).
     */
    post: operations['retryVideo']
    delete?: never
    options?: never
    head?: never
    patch?: never
    trace?: never
  }
  '/api/videos/{video_id}/reveal': {
    parameters: {
      query?: never
      header?: never
      path?: never
      cookie?: never
    }
    get?: never
    put?: never
    /**
     * Reveal
     * @description Show the file of a video selected in Finder (R-UI-10).
     */
    post: operations['revealVideo']
    delete?: never
    options?: never
    head?: never
    patch?: never
    trace?: never
  }
  '/api/videos/{video_id}/thumbnail': {
    parameters: {
      query?: never
      header?: never
      path?: never
      cookie?: never
    }
    /**
     * Get Thumbnail
     * @description Return the cached thumbnail of a video (R-CH-16).
     */
    get: operations['getVideoThumbnail']
    put?: never
    post?: never
    delete?: never
    options?: never
    head?: never
    patch?: never
    trace?: never
  }
  '/api/youtube/try-now': {
    parameters: {
      query?: never
      header?: never
      path?: never
      cookie?: never
    }
    get?: never
    put?: never
    /**
     * Try Youtube Now
     * @description End the pause of the app and take up the work that waited (R-ER-05).
     */
    post: operations['tryYouTubeNow']
    delete?: never
    options?: never
    head?: never
    patch?: never
    trace?: never
  }
}
export type webhooks = Record<string, never>
export interface components {
  schemas: {
    /**
     * AddChannelRequest
     * @description The body of ``POST /api/channels``: step 2 of the add channel dialog (R-CH-05).
     *
     *     Attributes:
     *         channel_id: The channel that was looked up.
     *         folder: A folder the folder dialog returned, or None for the default.
     *         quality: The quality of this channel, or None for "use default".
     *         auto_mirror: Whether everything is mirrored automatically.
     *         mirror_after: Auto-mirror only videos uploaded after this time, or None.
     */
    AddChannelRequest: {
      /**
       * Auto Mirror
       * @default false
       */
      auto_mirror: boolean
      /** Channel Id */
      channel_id: string
      /** Folder */
      folder?: string | null
      /** Mirror After */
      mirror_after?: number | null
      quality?: components['schemas']['Quality'] | null
    }
    /**
     * AddChannelResponse
     * @description The answer of ``POST /api/channels``.
     *
     *     Attributes:
     *         channel: The channel as it is now.
     *         existing: True when the channel was there already and nothing was added (R-CH-04).
     */
    AddChannelResponse: {
      channel: components['schemas']['Channel']
      /** Existing */
      existing: boolean
    }
    /**
     * ApiKey
     * @description How the optional YouTube API key stands (R-DT-12). Never the key itself.
     *
     *     Attributes:
     *         status: None saved, saved, or saved but unreadable, invalid or out of quota.
     *         until: Until when the app does without a failing key, or None.
     */
    ApiKey: {
      status: components['schemas']['KeyStatus']
      /** Until */
      until: number | null
    }
    /**
     * ApiKeyChangedEvent
     * @description The data of the ``apikey.changed`` event of ``GET /api/events``.
     *
     *     Attributes:
     *         api_key: How the key stands now (R-DT-12).
     */
    ApiKeyChangedEvent: {
      api_key: components['schemas']['ApiKey']
    }
    /**
     * AutoMirrorAnswer
     * @description The answers to the question before a large start of auto-mirror (D-095).
     * @enum {string}
     */
    AutoMirrorAnswer: 'mirror_all' | 'only_new' | 'turn_off'
    /**
     * AutoMirrorAnswerRequest
     * @description The body of ``POST /api/channels/{id}/auto-mirror/answer`` (D-095).
     *
     *     Attributes:
     *         answer: Mirror all, only new videos from now on, or turn auto-mirror off.
     */
    AutoMirrorAnswerRequest: {
      answer: components['schemas']['AutoMirrorAnswer']
    }
    /**
     * AutoMirrorQuestionInfo
     * @description Auto-mirror waits for the user before a large start (R-MI-02, D-095).
     *
     *     Attributes:
     *         count: How many videos it would download.
     *         estimated_bytes: About how much room they take.
     */
    AutoMirrorQuestionInfo: {
      /** Count */
      count: number
      /** Estimated Bytes */
      estimated_bytes: number
    }
    /**
     * AutoMirrorRequest
     * @description The body of ``PUT /api/channels/{id}/auto-mirror`` (R-MI-02).
     *
     *     Attributes:
     *         on: Whether auto-mirror is on.
     */
    AutoMirrorRequest: {
      /** On */
      on: boolean
    }
    /**
     * BannerChangedEvent
     * @description The data of the ``banner.changed`` event of ``GET /api/events``.
     *
     *     Attributes:
     *         youtube_pause: The pause of the whole app, or None when it ended (R-ER-05).
     */
    BannerChangedEvent: {
      youtube_pause: components['schemas']['Pause'] | null
    }
    /**
     * CancelCheckResponse
     * @description The answer of ``POST /api/channels/{id}/check/cancel``.
     *
     *     Attributes:
     *         cancelled: Whether there was a full check to cancel (R-CH-27).
     */
    CancelCheckResponse: {
      /** Cancelled */
      cancelled: boolean
    }
    /**
     * CancelJobResponse
     * @description The answer of ``POST /api/jobs/{id}/cancel`` (R-QU-02).
     *
     *     Attributes:
     *         cancelled: Whether there was a download that waited or ran.
     */
    CancelJobResponse: {
      /** Cancelled */
      cancelled: boolean
    }
    /**
     * ChangeChannelRequest
     * @description The body of ``PATCH /api/channels/{id}``. More fields arrive with channel settings in M7.
     *
     *     Attributes:
     *         paused: True to pause the channel, False to resume it (R-CH-31).
     */
    ChangeChannelRequest: {
      /** Paused */
      paused: boolean
    }
    /**
     * Channel
     * @description One channel as the interface shows it (R-CH-34, R-CH-35).
     *
     *     Attributes:
     *         id: The channel ID.
     *         title: The name of the channel.
     *         handle: The handle with its ``@``, or None.
     *         url: The address of the channel at YouTube.
     *         folder: The channel folder as an absolute path.
     *         folder_is_custom: Whether the user chose the folder.
     *         quality: The quality of this channel, or None for the default.
     *         auto_mirror: Whether auto-mirror is on.
     *         mirror_after: Auto-mirror only videos uploaded after this time, or None.
     *         paused: Whether the channel is paused.
     *         status: The one status line (R-FB-01).
     *         videos: How many videos the catalogue has.
     *         synced: How many of them are synced.
     *         excluded: How many of them are excluded.
     *         size_bytes: The size of the synced files together.
     *         new_videos: How many videos are new (R-CH-15).
     *         first_listed_at: When the first listing completed, or None while it has not.
     *         last_check_at: The last successful check of either kind, or None.
     *         last_full_check_at: The last successful full check, or None.
     *         last_check_error: The error code of the last check when it failed, or None.
     *         last_check_error_at: When that check failed, or None.
     *         progress: The first listing or full check that is running, or None.
     *         pictures: A number that grows when more pictures of the channel are cached.
     *         avatar_version: A number that grows when the avatar of the channel was cached anew.
     *         catalogue_version: A number that grows with every successful check of the channel.
     *         mirroring: While videos of the channel are downloaded, how many ended and how
     *             many there are (R-FB-01: "Mirroring X of Y"). Otherwise None.
     *         exact_dates: While dates of the channel wait to be looked up, how far they are
     *             ("Exact dates X of Y"), the time left and the key offer. Otherwise None.
     *         key_notice: Whether a saved API key is not working while dates of the channel
     *             wait (R-DT-12): "the API key is not working, using the slow way".
     *         waiting_until: When the exact dates go on, while they wait for YouTube.
     *         retry_at: When a failed check is tried again by itself (R-CH-25), or None.
     *         auto_mirror_question: What auto-mirror would start and waits for an answer
     *             about (D-095), or None.
     *         missing_held: How many missing files auto-mirror waits for an answer about
     *             (D-092), or None.
     */
    Channel: {
      /** Auto Mirror */
      auto_mirror: boolean
      auto_mirror_question?: components['schemas']['AutoMirrorQuestionInfo'] | null
      /** Avatar Version */
      avatar_version: number
      /** Catalogue Version */
      catalogue_version: number
      exact_dates?: components['schemas']['ExactDates'] | null
      /** Excluded */
      excluded: number
      /** First Listed At */
      first_listed_at: number | null
      /** Folder */
      folder: string
      /** Folder Is Custom */
      folder_is_custom: boolean
      /** Handle */
      handle: string | null
      /** Id */
      id: string
      /**
       * Key Notice
       * @default false
       */
      key_notice: boolean
      /** Last Check At */
      last_check_at: number | null
      last_check_error: components['schemas']['ErrorCode'] | null
      /** Last Check Error At */
      last_check_error_at: number | null
      /** Last Full Check At */
      last_full_check_at: number | null
      /** Mirror After */
      mirror_after: number | null
      mirroring?: components['schemas']['Mirroring'] | null
      /** Missing Held */
      missing_held?: number | null
      /** New Videos */
      new_videos: number
      /** Paused */
      paused: boolean
      /** Pictures */
      pictures: number
      progress: components['schemas']['Progress'] | null
      quality: components['schemas']['Quality'] | null
      /** Retry At */
      retry_at?: number | null
      /** Size Bytes */
      size_bytes: number
      status: components['schemas']['ChannelStatus']
      /** Synced */
      synced: number
      /** Title */
      title: string
      /** Url */
      url: string
      /** Videos */
      videos: number
      /** Waiting Until */
      waiting_until?: number | null
    }
    /**
     * ChannelStatus
     * @description The one status line of a channel (R-FB-01). Derived, never stored.
     *
     *     Each milestone adds the statuses that can occur from it on.
     * @enum {string}
     */
    ChannelStatus:
      | 'mirroring'
      | 'checking'
      | 'exact_dates'
      | 'waiting_for_youtube'
      | 'folder_not_found'
      | 'could_not_check'
      | 'new_videos'
      | 'paused'
      | 'up_to_date'
    /**
     * ChannelUpdatedEvent
     * @description The data of the ``channel.updated`` event of ``GET /api/events``.
     *
     *     Attributes:
     *         channel: The channel as it is now.
     */
    ChannelUpdatedEvent: {
      channel: components['schemas']['Channel']
    }
    /**
     * ChapterInfo
     * @description One chapter of a video (R-UI-08).
     *
     *     Attributes:
     *         start_s: Where it starts, in seconds.
     *         title: Its title.
     */
    ChapterInfo: {
      /** Start S */
      start_s: number
      /** Title */
      title: string
    }
    /**
     * CheckAllResponse
     * @description The answer of ``POST /api/channels/check-all``.
     *
     *     Attributes:
     *         channels: How many channels are being checked.
     */
    CheckAllResponse: {
      /** Channels */
      channels: number
    }
    /**
     * CheckKind
     * @description The two kinds of check (R-CH-12, docs/DECISIONS.md D-059).
     * @enum {string}
     */
    CheckKind: 'quick' | 'full'
    /**
     * CheckRequest
     * @description The body of ``POST /api/channels/{id}/check``.
     *
     *     Attributes:
     *         kind: A quick check ("Check now") or a full check (R-CH-23).
     *         trigger: What the user pressed: the button, the menu, or "Try again". It is
     *             logged with the check, so the log alone tells why it ran.
     */
    CheckRequest: {
      /** @default quick */
      kind: components['schemas']['CheckKind']
      /** @default api */
      trigger: components['schemas']['CheckTrigger']
    }
    /**
     * CheckTrigger
     * @description What started a check. Logged with every check, so the log alone tells why it ran.
     * @enum {string}
     */
    CheckTrigger:
      | 'button'
      | 'menu'
      | 'check_all'
      | 'retry'
      | 'add'
      | 'app_start'
      | 'resume'
      | 'schedule'
      | 'api'
    /**
     * ChecksProgressEvent
     * @description The data of the ``checks.progress`` event of ``GET /api/events``.
     *
     *     Attributes:
     *         checking_all: How many checks of a check of all channels ended, and how many
     *             there are, or None when it ended (R-CH-20: "Checking channels: 3 of 5").
     */
    ChecksProgressEvent: {
      checking_all: components['schemas']['Mirroring'] | null
    }
    /**
     * ChosenFolderResponse
     * @description The answer of ``POST /api/folders/choose``.
     *
     *     Attributes:
     *         folder: The folder the user chose, or None after Cancel.
     *         video_files: How many video files it already contains (R-CH-06).
     */
    ChosenFolderResponse: {
      /** Folder */
      folder: string | null
      /** Video Files */
      video_files: number
    }
    /**
     * ClearWaitingResponse
     * @description The answer of ``POST /api/queue/clear-waiting`` (R-QU-02).
     *
     *     Attributes:
     *         removed: How many waiting downloads were removed.
     */
    ClearWaitingResponse: {
      /** Removed */
      removed: number
    }
    /**
     * DateInfo
     * @description What an approximate date shows (R-DT-13).
     *
     *     Attributes:
     *         state: Waiting, updating or unavailable.
     *         reason: Why it is unavailable, or None.
     *         retry_at: When it is tried again, or None.
     */
    DateInfo: {
      reason: components['schemas']['ErrorCode'] | null
      /** Retry At */
      retry_at: number | null
      state: components['schemas']['DateState']
    }
    /**
     * DatePrecision
     * @description The unit YouTube gave an approximate date in (R-DT-04, docs/GLOSSARY.md).
     * @enum {string}
     */
    DatePrecision: 'day' | 'week' | 'month' | 'year'
    /**
     * DateState
     * @description What the approximate date of a video shows (R-DT-13).
     * @enum {string}
     */
    DateState: 'waiting' | 'updating' | 'unavailable'
    /**
     * DiskGuard
     * @description The queue is paused because a disk has too little free space (R-QU-10).
     *
     *     Attributes:
     *         disk: The name of the volume.
     *         free_bytes: Its free space when the guard saw it.
     *         limit_bytes: The free space below which the queue pauses.
     */
    DiskGuard: {
      /** Disk */
      disk: string
      /** Free Bytes */
      free_bytes: number
      /** Limit Bytes */
      limit_bytes: number
    }
    /**
     * DiskSpace
     * @description The disk the library is on (R-UI-01).
     *
     *     Attributes:
     *         name: The name of the volume.
     *         free_bytes: How much room is left on it.
     */
    DiskSpace: {
      /** Free Bytes */
      free_bytes: number
      /** Name */
      name: string
    }
    /**
     * Download
     * @description How far the running download of a video is (R-QU-04).
     *
     *     Attributes:
     *         job_id: The job.
     *         video_id: The video.
     *         channel_id: Its channel.
     *         stage: Video, audio or processing.
     *         fraction: How much of the whole video is done, its streams together, from 0
     *             to 1. None while it is processed, or when a size is not known.
     *         speed_bps: Bytes per second, or None.
     *         left_s: Seconds left of the download, or None.
     *         height: The height being downloaded, or None.
     *         downloaded_bytes: How many bytes arrived, all parts together, or None.
     *         total_bytes: How many bytes all parts have, real or estimated, or None.
     *         parts: Each part: video, audio, subtitles, thumbnail (R-QU-04).
     *         again: Whether this is a second download without subtitles (R-MD-04).
     */
    Download: {
      /**
       * Again
       * @default false
       */
      again: boolean
      /** Channel Id */
      channel_id: string
      /** Downloaded Bytes */
      downloaded_bytes: number | null
      /** Fraction */
      fraction: number | null
      /** Height */
      height: number | null
      /** Job Id */
      job_id: string
      /** Left S */
      left_s: number | null
      /**
       * Parts
       * @default []
       */
      parts: components['schemas']['DownloadPart'][]
      /** Speed Bps */
      speed_bps: number | null
      stage: components['schemas']['Stage']
      /** Total Bytes */
      total_bytes?: number | null
      /** Video Id */
      video_id: string
    }
    /**
     * DownloadPart
     * @description One part of a running download, for the details panel (R-QU-04).
     *
     *     Attributes:
     *         kind: Video, audio, subtitles or thumbnail.
     *         size: Its size in bytes, real or estimated.
     *         done: How many of its bytes arrived.
     *         estimated: Whether the size is an estimate.
     *         finished: Whether it is complete.
     */
    DownloadPart: {
      /** Done */
      done: number
      /** Estimated */
      estimated: boolean
      /** Finished */
      finished: boolean
      kind: components['schemas']['PartKind']
      /** Size */
      size: number
    }
    /**
     * ErrorBody
     * @description The content of every error response.
     *
     *     Attributes:
     *         code: The stable error code (docs/LOGGING.md section 4). Typed, so that the
     *             generated frontend types know every code.
     *         message: A short technical sentence. User text is written per code in the frontend.
     *         details: Extra facts for the technical details.
     */
    ErrorBody: {
      code: components['schemas']['ErrorCode']
      /** Details */
      details: {
        [key: string]: string
      }
      /** Message */
      message: string
    }
    /**
     * ErrorCode
     * @description Stable error codes. The value is what appears in logs and API responses.
     * @enum {string}
     */
    ErrorCode:
      | 'UNAUTHORIZED'
      | 'ORIGIN_REJECTED'
      | 'NOT_FOUND'
      | 'INVALID_REQUEST'
      | 'LOCAL_SERVER_UNREACHABLE'
      | 'NETWORK_UNREACHABLE'
      | 'RATE_LIMITED'
      | 'BOT_CHECK'
      | 'YOUTUBE_CHANGED'
      | 'CHANNEL_NOT_FOUND'
      | 'INVALID_CHANNEL_INPUT'
      | 'FOLDER_UNAVAILABLE'
      | 'PERMISSION_DENIED'
      | 'CHECKSUM_MISMATCH'
      | 'DISK_FULL'
      | 'TOOL_MISSING'
      | 'VIDEO_PRIVATE'
      | 'VIDEO_REMOVED'
      | 'MEMBERS_ONLY'
      | 'AGE_RESTRICTED'
      | 'GEO_BLOCKED'
      | 'NOT_YET_AVAILABLE'
      | 'NO_FORMATS'
      | 'FFMPEG_FAILED'
      | 'VERIFY_FAILED'
      | 'DATES_NOT_APPLIED'
      | 'DB_UPGRADE_FAILED'
      | 'CHANNEL_BUSY'
      | 'DB_UNREADABLE'
      | 'API_KEY_INVALID'
      | 'API_QUOTA_EXCEEDED'
      | 'API_KEY_UNREADABLE'
      | 'FILE_MISSING'
      | 'INTERNAL'
    /**
     * ErrorResponse
     * @description The one shape of every error response.
     */
    ErrorResponse: {
      error: components['schemas']['ErrorBody']
    }
    EventData:
      | components['schemas']['ToolUpdatedEvent']
      | components['schemas']['ChannelUpdatedEvent']
      | components['schemas']['TaskProgressEvent']
      | components['schemas']['BannerChangedEvent']
      | components['schemas']['VideoUpdatedEvent']
      | components['schemas']['VideosChangedEvent']
      | components['schemas']['JobProgressEvent']
      | components['schemas']['ApiKeyChangedEvent']
      | components['schemas']['ChecksProgressEvent']
      | components['schemas']['QueueUpdatedEvent']
      | components['schemas']['MenuCommandEvent']
      | components['schemas']['QuitAskedEvent']
    /**
     * ExactDates
     * @description How far the exact dates of a channel are (R-FB-01, R-DT-14, R-DT-15).
     *
     *     Attributes:
     *         done: How many dates were found since the channel last had none waiting.
     *         total: How many there are in all since then.
     *         left_s: The measured time left, or None while it is not known.
     *         offer_key: Whether the channel offers the key.
     */
    ExactDates: {
      /** Done */
      done: number
      /** Left S */
      left_s: number | null
      /** Offer Key */
      offer_key: boolean
      /** Total */
      total: number
    }
    /**
     * FailedItem
     * @description One failed video, as the downloads panel shows it (R-QU-08).
     *
     *     Attributes:
     *         video_id: The video.
     *         channel_id: Its channel.
     *         channel_title: The name of the channel.
     *         title: The title of the video.
     *         error_code: Why it failed, or None.
     *         attempts: How many automatic attempts were made since it last succeeded.
     *         gone: Whether YouTube no longer has it: then it offers no Retry (R-CH-14).
     */
    FailedItem: {
      /** Attempts */
      attempts: number
      /** Channel Id */
      channel_id: string
      /** Channel Title */
      channel_title: string
      error_code: components['schemas']['ErrorCode'] | null
      /** Gone */
      gone: boolean
      /** Title */
      title: string
      /** Video Id */
      video_id: string
    }
    /**
     * FileFacts
     * @description The file of a synced video, as the details panel shows it (R-UI-08).
     *
     *     Attributes:
     *         name: The file name.
     *         size: Its size in bytes.
     *         width: The width of the video, or None.
     *         height: The height of the video, or None.
     *         fps: Frames per second, or None.
     *         vcodec: The video codec, or None.
     *         acodec: The audio codec, or None.
     *         audio_channels: The number of audio channels, or None.
     *         subtitles: ``manual``, ``auto`` or None.
     *         cover_embedded: Whether the thumbnail is inside the file.
     */
    FileFacts: {
      /** Acodec */
      acodec: string | null
      /** Audio Channels */
      audio_channels: number | null
      /** Cover Embedded */
      cover_embedded: boolean
      /** Fps */
      fps: number | null
      /** Height */
      height: number | null
      /** Name */
      name: string
      /** Size */
      size: number | null
      /** Subtitles */
      subtitles: string | null
      /** Vcodec */
      vcodec: string | null
      /** Width */
      width: number | null
    }
    /**
     * FilesToTrashResponse
     * @description The answer of ``GET /api/channels/{id}/files-to-trash`` (R-CH-32).
     *
     *     Attributes:
     *         files: How many visible files "Delete the files" moves to the Trash.
     *         size_bytes: How much room they take, the hidden folder of the app included.
     */
    FilesToTrashResponse: {
      /** Files */
      files: number
      /** Size Bytes */
      size_bytes: number
    }
    /** HTTPValidationError */
    HTTPValidationError: {
      /** Detail */
      detail?: components['schemas']['ValidationError'][]
    }
    /**
     * HealthResponse
     * @description The answer of ``GET /api/health``.
     *
     *     Attributes:
     *         status: Always ``ok`` when the server answers.
     *         version: The app version.
     *         schema_version: The database schema version.
     */
    HealthResponse: {
      /** Schema Version */
      schema_version: string | null
      /**
       * Status
       * @constant
       */
      status: 'ok'
      /** Version */
      version: string
    }
    /**
     * JobProgressEvent
     * @description The data of the ``job.progress`` event of ``GET /api/events`` (R-QU-04).
     *
     *     Attributes:
     *         download: How far the download is.
     */
    JobProgressEvent: {
      download: components['schemas']['Download']
    }
    /**
     * KeptFileResponse
     * @description A file that "Delete the files" left in the folder, and why (R-CH-32).
     *
     *     Attributes:
     *         file: The path, relative to the channel folder.
     *         reason: ``trash_refused`` (macOS refused), ``another_video`` (another
     *             video is inside), ``not_checked`` (the video inside could not be
     *             read) or ``outside_folder`` (it leads out of the folder).
     */
    KeptFileResponse: {
      /** File */
      file: string
      reason: components['schemas']['KeptReason']
    }
    /**
     * KeptReason
     * @description Why "Delete the files" left a file in the folder (R-CH-32).
     * @enum {string}
     */
    KeptReason: 'trash_refused' | 'another_video' | 'not_checked' | 'outside_folder'
    /**
     * KeyStatus
     * @description How the optional API key stands (R-DT-12).
     * @enum {string}
     */
    KeyStatus: 'none' | 'saved' | 'unreadable' | 'invalid' | 'quota_exceeded'
    /**
     * LookupRequest
     * @description The body of ``POST /api/channels/lookup``.
     *
     *     Attributes:
     *         text: What the user pasted or typed (R-CH-01).
     */
    LookupRequest: {
      /** Text */
      text: string
    }
    /**
     * LookupResponse
     * @description The preview of a channel before the user confirms (R-CH-03 to R-CH-06).
     *
     *     The video count is not in it: it is fetched apart, so it never delays the preview.
     *
     *     Attributes:
     *         channel_id: The channel ID.
     *         title: The name of the channel.
     *         handle: The handle with its ``@``, or None.
     *         has_avatar: Whether the channel has an avatar to show.
     *         existing: Whether the channel was added before (R-CH-04).
     *         folder: The folder the channel gets when the user chooses none.
     *         video_files: How many video files that folder already contains (R-CH-06).
     */
    LookupResponse: {
      /** Channel Id */
      channel_id: string
      /** Existing */
      existing: boolean
      /** Folder */
      folder: string
      /** Handle */
      handle: string | null
      /** Has Avatar */
      has_avatar: boolean
      /** Title */
      title: string
      /** Video Files */
      video_files: number
    }
    /**
     * MenuCommand
     * @description A command of the menu bar, which the interface runs as its own control does (D-094).
     * @enum {string}
     */
    MenuCommand:
      | 'add_channel'
      | 'view_list'
      | 'view_grid'
      | 'show_downloads'
      | 'reload'
      | 'check_now'
      | 'check_all'
      | 'mirror_missing'
      | 'toggle_pause'
      | 'open_folder'
      | 'shortcuts'
    /**
     * MenuCommandEvent
     * @description Data of the event ``menu.command``: run the command of a menu item (D-094).
     */
    MenuCommandEvent: {
      command: components['schemas']['MenuCommand']
    }
    /**
     * MirrorRequest
     * @description The body of ``POST /api/videos/mirror`` (R-MI-01).
     *
     *     Attributes:
     *         ids: The videos to put in line, in this order.
     *         first: Whether they go to the top of the line ("Mirror first", R-QU-02).
     */
    MirrorRequest: {
      /**
       * First
       * @default false
       */
      first: boolean
      /** Ids */
      ids: string[]
    }
    /**
     * MirrorResponse
     * @description The answer of ``POST /api/videos/mirror``.
     *
     *     Attributes:
     *         jobs: The downloads that were put in line. A video that waits, runs or is
     *             synced already is left out.
     */
    MirrorResponse: {
      /** Jobs */
      jobs: components['schemas']['QueuedJob'][]
    }
    /**
     * Mirroring
     * @description How far the downloads of a channel are (R-FB-01).
     *
     *     Attributes:
     *         done: How many ended, well or not.
     *         total: How many there are in all.
     */
    Mirroring: {
      /** Done */
      done: number
      /** Total */
      total: number
    }
    /**
     * OpenChannelRequest
     * @description The body of ``PUT /api/state/open-channel``.
     *
     *     Attributes:
     *         channel_id: The channel the user has open, or None for no channel.
     */
    OpenChannelRequest: {
      /** Channel Id */
      channel_id: string | null
    }
    /**
     * PartKind
     * @description What a part of a download is.
     * @enum {string}
     */
    PartKind: 'video' | 'audio' | 'subtitles' | 'thumbnail'
    /**
     * Pause
     * @description The pause of what the app asks of YouTube by itself (R-ER-05).
     *
     *     Attributes:
     *         code: Why the app pauses.
     *         until: When it tries again, as seconds since the epoch.
     */
    Pause: {
      code: components['schemas']['ErrorCode']
      /** Until */
      until: number
    }
    /**
     * Progress
     * @description How far a first listing or a full check has come (R-CH-11, R-CH-27).
     *
     *     Attributes:
     *         channel_id: The channel.
     *         kind: What is running.
     *         done: How many videos were read so far.
     *         total: About how many there are, or None when the catalogue had none.
     */
    Progress: {
      /** Channel Id */
      channel_id: string
      /** Done */
      done: number
      kind: components['schemas']['TaskKind']
      /** Total */
      total: number | null
    }
    /**
     * Quality
     * @description The quality a channel asks for (R-QL-01). Its rules are in ``core/quality.py``.
     * @enum {string}
     */
    Quality: 'best' | '2160' | '1440' | '1080' | '720' | '480'
    /**
     * Queue
     * @description How the queue stands, for the queue bar (R-QU-01, R-QU-02).
     *
     *     Attributes:
     *         downloading: How many downloads run now.
     *         waiting: How many wait in line.
     *         failed: How many videos failed (R-QU-08).
     *         paused: Whether the user paused all downloads.
     *         places: How many downloads may run at once.
     *         speed_limit_mbps: The limit of all downloads together, 0 for none (R-QU-03).
     *         disk_guard: The pause of the disk space guard, or None (R-QU-10).
     *         folders_away: The channels whose folder cannot be reached (R-QU-11).
     */
    Queue: {
      disk_guard?: components['schemas']['DiskGuard'] | null
      /** Downloading */
      downloading: number
      /** Failed */
      failed: number
      /**
       * Folders Away
       * @default []
       */
      folders_away: string[]
      /** Paused */
      paused: boolean
      /** Places */
      places: number
      /**
       * Speed Limit Mbps
       * @default 0
       */
      speed_limit_mbps: number
      /** Waiting */
      waiting: number
    }
    /**
     * QueueItem
     * @description One download that waits or runs, as the downloads panel shows it (R-QU-02).
     *
     *     Attributes:
     *         job_id: The job.
     *         video_id: The video.
     *         channel_id: Its channel.
     *         channel_title: The name of the channel.
     *         title: The title of the video.
     *         duration_s: Its length in seconds, or None.
     *         quality: The quality it is downloaded in.
     *         by_hand: Whether the user started it by hand (R-DT-06, D-090).
     *         download: How far it is, when it runs and reported already, else None.
     *         paced_until: When it may start, while it waits for room in the lookup
     *             budget (D-090), else None.
     */
    QueueItem: {
      /** By Hand */
      by_hand: boolean
      /** Channel Id */
      channel_id: string
      /** Channel Title */
      channel_title: string
      download?: components['schemas']['Download'] | null
      /** Duration S */
      duration_s: number | null
      /** Job Id */
      job_id: string
      /** Paced Until */
      paced_until?: number | null
      quality: components['schemas']['Quality']
      /** Title */
      title: string
      /** Video Id */
      video_id: string
    }
    /**
     * QueueResponse
     * @description The answer of ``GET /api/queue``: the whole queue (R-QU-02).
     *
     *     Attributes:
     *         queue: How it stands.
     *         running: The downloads that run.
     *         waiting: The downloads that wait, in their order.
     *         failed: The failed videos, newest failure first.
     */
    QueueResponse: {
      /** Failed */
      failed: components['schemas']['FailedItem'][]
      queue: components['schemas']['Queue']
      /** Running */
      running: components['schemas']['QueueItem'][]
      /** Waiting */
      waiting: components['schemas']['QueueItem'][]
    }
    /**
     * QueueUpdatedEvent
     * @description The data of the event ``queue.updated``: the queue changed (R-FB-03).
     *
     *     Attributes:
     *         queue: How it stands now.
     */
    QueueUpdatedEvent: {
      queue: components['schemas']['Queue']
    }
    /**
     * QueuedJob
     * @description A download that was put in line.
     *
     *     Attributes:
     *         job_id: The job.
     *         video_id: The video.
     */
    QueuedJob: {
      /** Job Id */
      job_id: string
      /** Video Id */
      video_id: string
    }
    /**
     * QuitAskedEvent
     * @description Data of the event ``quit.asked``: a quit waits while downloads run; ask (R-QU-12).
     */
    QuitAskedEvent: Record<string, never>
    /**
     * RemovedChannelResponse
     * @description The answer of ``DELETE /api/channels/{id}`` (R-CH-32).
     *
     *     Attributes:
     *         folder: The folder of the channel.
     *         files_trashed: How many files and folders went to the Trash.
     *         left: Every file that should have gone to the Trash and stayed, with
     *             its reason. Empty when every file went, or when the files were kept.
     */
    RemovedChannelResponse: {
      /** Files Trashed */
      files_trashed: number
      /** Folder */
      folder: string
      /** Left */
      left: components['schemas']['KeptFileResponse'][]
    }
    /**
     * ReorderRequest
     * @description The body of ``POST /api/queue/reorder`` (R-QU-02).
     *
     *     Attributes:
     *         job_ids: The waiting jobs in the order the user wants.
     */
    ReorderRequest: {
      /** Job Ids */
      job_ids: string[]
    }
    /**
     * RepairDatesResponse
     * @description The answer of ``POST /api/channels/{channel_id}/repair-dates`` (R-DT-09).
     *
     *     Attributes:
     *         checked: How many synced files were compared.
     *         repaired: How many had other dates and were set again.
     *         failed: How many could not be set or did not read back.
     */
    RepairDatesResponse: {
      /** Checked */
      checked: number
      /** Failed */
      failed: number
      /** Repaired */
      repaired: number
    }
    /**
     * SaveApiKeyRequest
     * @description The body of ``PUT /api/settings/api-key``.
     *
     *     Attributes:
     *         key: The key as the user pasted it. Never logged or stored outside its file.
     */
    SaveApiKeyRequest: {
      /** Key */
      key: string
    }
    /**
     * SpeedLimitRequest
     * @description The body of ``POST /api/queue/speed-limit`` (R-QU-03).
     *
     *     Attributes:
     *         mbps: The limit of all downloads together in MB/s: 0 (unlimited), 5, 2 or 1.
     */
    SpeedLimitRequest: {
      /** Mbps */
      mbps: number
    }
    /**
     * Stage
     * @description What a running download does now (R-QU-04).
     * @enum {string}
     */
    Stage: 'video' | 'audio' | 'processing'
    /**
     * StateResponse
     * @description The answer of ``GET /api/state``: the app as the window draws it.
     *
     *     Attributes:
     *         channels: Every channel, in the order of the sidebar.
     *         open_channel_id: The channel that was open last, or None (R-UI-02).
     *         library_folder: The library folder as a path.
     *         disk: The disk the library is on.
     *         can_choose_folder: Whether the folder dialog of macOS can be shown.
     *         youtube_pause: The pause of the whole app, or None (R-ER-05).
     *         api_key: How the optional API key stands (R-DT-12).
     *         checking_all: How far a check of all channels is ("Checking channels: 3 of 5"),
     *             or None (R-CH-20).
     *         queue: How the queue of downloads stands (R-QU-02).
     *         view: Whether channels show their videos as a list or a grid (R-UI-03).
     */
    StateResponse: {
      api_key: components['schemas']['ApiKey']
      /** Can Choose Folder */
      can_choose_folder: boolean
      /** Channels */
      channels: components['schemas']['Channel'][]
      checking_all?: components['schemas']['Mirroring'] | null
      disk: components['schemas']['DiskSpace']
      /** Library Folder */
      library_folder: string
      /** Open Channel Id */
      open_channel_id: string | null
      /**
       * @default {
       *       "downloading": 0,
       *       "failed": 0,
       *       "folders_away": [],
       *       "paused": false,
       *       "places": 2,
       *       "speed_limit_mbps": 0,
       *       "waiting": 0
       *     }
       */
      queue: components['schemas']['Queue']
      /** @default list */
      view: components['schemas']['ViewKind']
      youtube_pause: components['schemas']['Pause'] | null
    }
    /**
     * TaskKind
     * @description Long work on a channel whose progress is shown (R-CH-11, R-CH-27).
     * @enum {string}
     */
    TaskKind: 'first_listing' | 'full_check'
    /**
     * TaskProgressEvent
     * @description The data of the ``task.progress`` event of ``GET /api/events``.
     *
     *     Attributes:
     *         progress: How far a first listing or a full check has come.
     */
    TaskProgressEvent: {
      progress: components['schemas']['Progress']
    }
    /**
     * TestApiKeyRequest
     * @description The body of ``POST /api/settings/api-key/test``.
     *
     *     Attributes:
     *         key: The key to test, or None for the saved key.
     */
    TestApiKeyRequest: {
      /** Key */
      key?: string | null
    }
    /**
     * TestApiKeyResponse
     * @description The answer of "Test key" (R-DT-12).
     *
     *     Attributes:
     *         works: Whether the YouTube API answered with the key.
     *         error_code: Why not, or None.
     *         api_key: How the saved key stands now.
     */
    TestApiKeyResponse: {
      api_key: components['schemas']['ApiKey']
      error_code: components['schemas']['ErrorCode'] | null
      /** Works */
      works: boolean
    }
    /**
     * Tool
     * @description The state of one tool the app needs (R-IN-03, R-IN-04).
     *
     *     Attributes:
     *         name: The tool.
     *         status: What is known about it right now.
     *         version: Its version, when it is installed.
     *         source: The source it was downloaded from, for a downloaded tool.
     *         progress: How much of its download is done, from 0 to 1, while it installs.
     *         error_code: Why the last installation failed, when it did.
     *         installable: Whether the app can install it by itself.
     */
    Tool: {
      error_code: components['schemas']['ErrorCode'] | null
      /** Installable */
      installable: boolean
      name: components['schemas']['ToolName']
      /** Progress */
      progress: number | null
      /** Source */
      source: string | null
      status: components['schemas']['ToolStatus']
      /** Version */
      version: string | null
    }
    /**
     * ToolName
     * @description The tools the app needs, in the order the first-run screen shows them (R-IN-03).
     * @enum {string}
     */
    ToolName: 'python' | 'ytdlp' | 'ffmpeg' | 'deno'
    /**
     * ToolStatus
     * @description What is known about a tool right now (R-IN-03, R-IN-04).
     * @enum {string}
     */
    ToolStatus: 'ok' | 'missing' | 'broken' | 'installing' | 'failed'
    /**
     * ToolUpdatedEvent
     * @description The data of the ``tool.updated`` event of ``GET /api/events``.
     *
     *     Attributes:
     *         tool: The new state of the tool.
     *         setup_required: Whether the first-run screen is still needed.
     */
    ToolUpdatedEvent: {
      /** Setup Required */
      setup_required: boolean
      tool: components['schemas']['Tool']
    }
    /**
     * ToolsResponse
     * @description The answer of ``GET /api/tools``.
     *
     *     Attributes:
     *         tools: Every tool, in the order of the first-run screen.
     *         setup_required: Whether the interface must show the first-run screen.
     */
    ToolsResponse: {
      /** Setup Required */
      setup_required: boolean
      /** Tools */
      tools: components['schemas']['Tool'][]
    }
    /**
     * TryFolderResponse
     * @description The answer of ``POST /api/queue/folders/{channel_id}/try-again`` (R-QU-11).
     *
     *     Attributes:
     *         available: Whether the folder can be reached now: then its downloads go on.
     */
    TryFolderResponse: {
      /** Available */
      available: boolean
    }
    /**
     * UiStateRequest
     * @description What the interface tells the app about itself, for the menu bar (R-NA-04).
     */
    UiStateRequest: {
      /** Any Unpaused */
      any_unpaused: boolean
      /** Channel Open */
      channel_open: boolean
      /** Checking */
      checking: boolean
      /** Folder Available */
      folder_available: boolean
      /** Has Missing */
      has_missing: boolean
      /** Paused */
      paused: boolean
      view: components['schemas']['ViewKind']
    }
    /** ValidationError */
    ValidationError: {
      /** Context */
      ctx?: Record<string, never>
      /** Input */
      input?: unknown
      /** Location */
      loc: (string | number)[]
      /** Message */
      msg: string
      /** Error Type */
      type: string
    }
    /**
     * Video
     * @description One video of a catalogue, with the fields a list needs (R-CH-10).
     *
     *     Attributes:
     *         id: The video ID.
     *         title: The title.
     *         duration_s: The length in seconds, or None.
     *         view_count: The number of views, or None.
     *         published_at: The exact published time, or None while it is not known exactly.
     *         published_around: For an approximate date, the moment to show it from (R-DT-04).
     *         published_precision: The unit of an approximate date, or None.
     *         status: The stored status.
     *         is_new: Whether the video counts as new (R-CH-15).
     *         gone: Whether it is removed from YouTube (R-CH-14).
     *         excluded: Whether it is excluded.
     *         job_id: The job of a download that waits or runs, for Cancel, or None.
     *         download: How far a running download is (R-QU-04), or None.
     *         height: The height of the file of a synced video (R-FB-02), or None.
     *         file_size: The size of its file in bytes, or None.
     *         error_code: Why the last download failed (R-QU-08), or None.
     *         date: What an approximate date shows (R-DT-13), or None for an exact date.
     *         paced_until: When an automatic download that waits for room in the lookup
     *             budget may start, or None (R-DT-06, D-090).
     *         retry_at: When a download that failed in a way that passes is tried again by
     *             itself, or None (R-QU-07).
     *         below_target: Whether the file is lower than the quality its channel asks for
     *             now (R-QL-07).
     */
    Video: {
      /**
       * Below Target
       * @default false
       */
      below_target: boolean
      date?: components['schemas']['DateInfo'] | null
      download?: components['schemas']['Download'] | null
      /** Duration S */
      duration_s: number | null
      error_code?: components['schemas']['ErrorCode'] | null
      /** Excluded */
      excluded: boolean
      /** File Size */
      file_size?: number | null
      /** Gone */
      gone: boolean
      /** Height */
      height?: number | null
      /** Id */
      id: string
      /** Is New */
      is_new: boolean
      /** Job Id */
      job_id?: string | null
      /** Paced Until */
      paced_until?: number | null
      /** Published Around */
      published_around: number | null
      /** Published At */
      published_at: number | null
      published_precision: components['schemas']['DatePrecision'] | null
      /** Retry At */
      retry_at?: number | null
      status: components['schemas']['VideoStatus']
      /** Title */
      title: string
      /** View Count */
      view_count: number | null
    }
    /**
     * VideoCountResponse
     * @description The answer of ``GET /api/channels/lookup/{id}/video-count``.
     *
     *     Attributes:
     *         video_count: The number of videos of the preview, or None when YouTube
     *             gave none in time (R-CH-03).
     */
    VideoCountResponse: {
      /** Video Count */
      video_count: number | null
    }
    /**
     * VideoDetailsResponse
     * @description The answer of ``GET /api/videos/{id}``: everything the details panel shows (R-UI-08).
     *
     *     Attributes:
     *         video: The video as a list shows it.
     *         channel_id: Its channel.
     *         folder: The channel folder.
     *         file: The file of a synced video, or None.
     *         downloaded_at: When the file was completed, or None.
     *         description: The description from the saved metadata, or None.
     *         chapters: The chapters from the saved metadata.
     *         thumbnail_saved: Whether the original thumbnail is in the hidden folder.
     *         url: The address of the video on YouTube.
     */
    VideoDetailsResponse: {
      /** Channel Id */
      channel_id: string
      /** Chapters */
      chapters: components['schemas']['ChapterInfo'][]
      /** Description */
      description: string | null
      /** Downloaded At */
      downloaded_at: number | null
      file: components['schemas']['FileFacts'] | null
      /** Folder */
      folder: string
      /** Thumbnail Saved */
      thumbnail_saved: boolean
      /** Url */
      url: string
      video: components['schemas']['Video']
    }
    /**
     * VideoStatus
     * @description The stored status of a video (docs/ARCHITECTURE.md section 6.1).
     * @enum {string}
     */
    VideoStatus:
      | 'not_downloaded'
      | 'queued'
      | 'downloading'
      | 'processing'
      | 'synced'
      | 'file_missing'
      | 'failed'
    /**
     * VideoUpdatedEvent
     * @description The data of the ``video.updated`` event of ``GET /api/events`` (R-FB-03).
     *
     *     Attributes:
     *         channel_id: The channel of the video.
     *         video: The video as a list shows it now.
     */
    VideoUpdatedEvent: {
      /** Channel Id */
      channel_id: string
      video: components['schemas']['Video']
    }
    /**
     * VideosChangedEvent
     * @description The data of the ``videos.changed`` event: many videos of a channel changed at once.
     *
     *     The window loads the list of the channel again (R-FB-03).
     *
     *     Attributes:
     *         channel_id: The channel.
     *         count: How many videos changed.
     */
    VideosChangedEvent: {
      /** Channel Id */
      channel_id: string
      /** Count */
      count: number
    }
    /**
     * VideosResponse
     * @description The answer of ``GET /api/channels/{id}/videos``.
     *
     *     Attributes:
     *         videos: The catalogue in the order of the channel, newest first.
     */
    VideosResponse: {
      /** Videos */
      videos: components['schemas']['Video'][]
    }
    /**
     * ViewKind
     * @description How a channel's videos are shown: as a list or as a grid (R-UI-03).
     * @enum {string}
     */
    ViewKind: 'list' | 'grid'
    /**
     * ViewRequest
     * @description The body of ``PUT /api/state/view`` (R-UI-03).
     *
     *     Attributes:
     *         view: List or grid.
     */
    ViewRequest: {
      view: components['schemas']['ViewKind']
    }
  }
  responses: never
  parameters: never
  requestBodies: never
  headers: never
  pathItems: never
}
export type $defs = Record<string, never>
export interface operations {
  addChannel: {
    parameters: {
      query?: never
      header?: never
      path?: never
      cookie?: never
    }
    requestBody: {
      content: {
        'application/json': components['schemas']['AddChannelRequest']
      }
    }
    responses: {
      /** @description Successful Response */
      201: {
        headers: {
          [name: string]: unknown
        }
        content: {
          'application/json': components['schemas']['AddChannelResponse']
        }
      }
      /** @description Unauthorized */
      401: {
        headers: {
          [name: string]: unknown
        }
        content: {
          'application/json': components['schemas']['ErrorResponse']
        }
      }
      /** @description Forbidden */
      403: {
        headers: {
          [name: string]: unknown
        }
        content: {
          'application/json': components['schemas']['ErrorResponse']
        }
      }
      /** @description Validation Error */
      422: {
        headers: {
          [name: string]: unknown
        }
        content: {
          'application/json': components['schemas']['HTTPValidationError']
        }
      }
      /** @description Internal Server Error */
      500: {
        headers: {
          [name: string]: unknown
        }
        content: {
          'application/json': components['schemas']['ErrorResponse']
        }
      }
    }
  }
  checkAllChannels: {
    parameters: {
      query?: never
      header?: never
      path?: never
      cookie?: never
    }
    requestBody?: never
    responses: {
      /** @description Successful Response */
      202: {
        headers: {
          [name: string]: unknown
        }
        content: {
          'application/json': components['schemas']['CheckAllResponse']
        }
      }
      /** @description Unauthorized */
      401: {
        headers: {
          [name: string]: unknown
        }
        content: {
          'application/json': components['schemas']['ErrorResponse']
        }
      }
      /** @description Forbidden */
      403: {
        headers: {
          [name: string]: unknown
        }
        content: {
          'application/json': components['schemas']['ErrorResponse']
        }
      }
      /** @description Internal Server Error */
      500: {
        headers: {
          [name: string]: unknown
        }
        content: {
          'application/json': components['schemas']['ErrorResponse']
        }
      }
    }
  }
  lookUpChannel: {
    parameters: {
      query?: never
      header?: never
      path?: never
      cookie?: never
    }
    requestBody: {
      content: {
        'application/json': components['schemas']['LookupRequest']
      }
    }
    responses: {
      /** @description Successful Response */
      200: {
        headers: {
          [name: string]: unknown
        }
        content: {
          'application/json': components['schemas']['LookupResponse']
        }
      }
      /** @description Unauthorized */
      401: {
        headers: {
          [name: string]: unknown
        }
        content: {
          'application/json': components['schemas']['ErrorResponse']
        }
      }
      /** @description Forbidden */
      403: {
        headers: {
          [name: string]: unknown
        }
        content: {
          'application/json': components['schemas']['ErrorResponse']
        }
      }
      /** @description Validation Error */
      422: {
        headers: {
          [name: string]: unknown
        }
        content: {
          'application/json': components['schemas']['HTTPValidationError']
        }
      }
      /** @description Internal Server Error */
      500: {
        headers: {
          [name: string]: unknown
        }
        content: {
          'application/json': components['schemas']['ErrorResponse']
        }
      }
    }
  }
  getPreviewAvatar: {
    parameters: {
      query?: never
      header?: never
      path: {
        channel_id: string
      }
      cookie?: never
    }
    requestBody?: never
    responses: {
      /** @description Successful Response */
      200: {
        headers: {
          [name: string]: unknown
        }
        content?: never
      }
      /** @description Unauthorized */
      401: {
        headers: {
          [name: string]: unknown
        }
        content: {
          'application/json': components['schemas']['ErrorResponse']
        }
      }
      /** @description Forbidden */
      403: {
        headers: {
          [name: string]: unknown
        }
        content: {
          'application/json': components['schemas']['ErrorResponse']
        }
      }
      /** @description Validation Error */
      422: {
        headers: {
          [name: string]: unknown
        }
        content: {
          'application/json': components['schemas']['HTTPValidationError']
        }
      }
      /** @description Internal Server Error */
      500: {
        headers: {
          [name: string]: unknown
        }
        content: {
          'application/json': components['schemas']['ErrorResponse']
        }
      }
    }
  }
  getPreviewVideoCount: {
    parameters: {
      query?: never
      header?: never
      path: {
        channel_id: string
      }
      cookie?: never
    }
    requestBody?: never
    responses: {
      /** @description Successful Response */
      200: {
        headers: {
          [name: string]: unknown
        }
        content: {
          'application/json': components['schemas']['VideoCountResponse']
        }
      }
      /** @description Unauthorized */
      401: {
        headers: {
          [name: string]: unknown
        }
        content: {
          'application/json': components['schemas']['ErrorResponse']
        }
      }
      /** @description Forbidden */
      403: {
        headers: {
          [name: string]: unknown
        }
        content: {
          'application/json': components['schemas']['ErrorResponse']
        }
      }
      /** @description Validation Error */
      422: {
        headers: {
          [name: string]: unknown
        }
        content: {
          'application/json': components['schemas']['HTTPValidationError']
        }
      }
      /** @description Internal Server Error */
      500: {
        headers: {
          [name: string]: unknown
        }
        content: {
          'application/json': components['schemas']['ErrorResponse']
        }
      }
    }
  }
  getChannel: {
    parameters: {
      query?: never
      header?: never
      path: {
        channel_id: string
      }
      cookie?: never
    }
    requestBody?: never
    responses: {
      /** @description Successful Response */
      200: {
        headers: {
          [name: string]: unknown
        }
        content: {
          'application/json': components['schemas']['Channel']
        }
      }
      /** @description Unauthorized */
      401: {
        headers: {
          [name: string]: unknown
        }
        content: {
          'application/json': components['schemas']['ErrorResponse']
        }
      }
      /** @description Forbidden */
      403: {
        headers: {
          [name: string]: unknown
        }
        content: {
          'application/json': components['schemas']['ErrorResponse']
        }
      }
      /** @description Validation Error */
      422: {
        headers: {
          [name: string]: unknown
        }
        content: {
          'application/json': components['schemas']['HTTPValidationError']
        }
      }
      /** @description Internal Server Error */
      500: {
        headers: {
          [name: string]: unknown
        }
        content: {
          'application/json': components['schemas']['ErrorResponse']
        }
      }
    }
  }
  removeChannel: {
    parameters: {
      query?: {
        keep_files?: boolean
      }
      header?: never
      path: {
        channel_id: string
      }
      cookie?: never
    }
    requestBody?: never
    responses: {
      /** @description Successful Response */
      200: {
        headers: {
          [name: string]: unknown
        }
        content: {
          'application/json': components['schemas']['RemovedChannelResponse']
        }
      }
      /** @description Unauthorized */
      401: {
        headers: {
          [name: string]: unknown
        }
        content: {
          'application/json': components['schemas']['ErrorResponse']
        }
      }
      /** @description Forbidden */
      403: {
        headers: {
          [name: string]: unknown
        }
        content: {
          'application/json': components['schemas']['ErrorResponse']
        }
      }
      /** @description Validation Error */
      422: {
        headers: {
          [name: string]: unknown
        }
        content: {
          'application/json': components['schemas']['HTTPValidationError']
        }
      }
      /** @description Internal Server Error */
      500: {
        headers: {
          [name: string]: unknown
        }
        content: {
          'application/json': components['schemas']['ErrorResponse']
        }
      }
    }
  }
  changeChannel: {
    parameters: {
      query?: never
      header?: never
      path: {
        channel_id: string
      }
      cookie?: never
    }
    requestBody: {
      content: {
        'application/json': components['schemas']['ChangeChannelRequest']
      }
    }
    responses: {
      /** @description Successful Response */
      200: {
        headers: {
          [name: string]: unknown
        }
        content: {
          'application/json': components['schemas']['Channel']
        }
      }
      /** @description Unauthorized */
      401: {
        headers: {
          [name: string]: unknown
        }
        content: {
          'application/json': components['schemas']['ErrorResponse']
        }
      }
      /** @description Forbidden */
      403: {
        headers: {
          [name: string]: unknown
        }
        content: {
          'application/json': components['schemas']['ErrorResponse']
        }
      }
      /** @description Validation Error */
      422: {
        headers: {
          [name: string]: unknown
        }
        content: {
          'application/json': components['schemas']['HTTPValidationError']
        }
      }
      /** @description Internal Server Error */
      500: {
        headers: {
          [name: string]: unknown
        }
        content: {
          'application/json': components['schemas']['ErrorResponse']
        }
      }
    }
  }
  setAutoMirror: {
    parameters: {
      query?: never
      header?: never
      path: {
        channel_id: string
      }
      cookie?: never
    }
    requestBody: {
      content: {
        'application/json': components['schemas']['AutoMirrorRequest']
      }
    }
    responses: {
      /** @description Successful Response */
      200: {
        headers: {
          [name: string]: unknown
        }
        content: {
          'application/json': components['schemas']['Channel']
        }
      }
      /** @description Unauthorized */
      401: {
        headers: {
          [name: string]: unknown
        }
        content: {
          'application/json': components['schemas']['ErrorResponse']
        }
      }
      /** @description Forbidden */
      403: {
        headers: {
          [name: string]: unknown
        }
        content: {
          'application/json': components['schemas']['ErrorResponse']
        }
      }
      /** @description Validation Error */
      422: {
        headers: {
          [name: string]: unknown
        }
        content: {
          'application/json': components['schemas']['HTTPValidationError']
        }
      }
      /** @description Internal Server Error */
      500: {
        headers: {
          [name: string]: unknown
        }
        content: {
          'application/json': components['schemas']['ErrorResponse']
        }
      }
    }
  }
  answerAutoMirror: {
    parameters: {
      query?: never
      header?: never
      path: {
        channel_id: string
      }
      cookie?: never
    }
    requestBody: {
      content: {
        'application/json': components['schemas']['AutoMirrorAnswerRequest']
      }
    }
    responses: {
      /** @description Successful Response */
      200: {
        headers: {
          [name: string]: unknown
        }
        content: {
          'application/json': components['schemas']['Channel']
        }
      }
      /** @description Unauthorized */
      401: {
        headers: {
          [name: string]: unknown
        }
        content: {
          'application/json': components['schemas']['ErrorResponse']
        }
      }
      /** @description Forbidden */
      403: {
        headers: {
          [name: string]: unknown
        }
        content: {
          'application/json': components['schemas']['ErrorResponse']
        }
      }
      /** @description Validation Error */
      422: {
        headers: {
          [name: string]: unknown
        }
        content: {
          'application/json': components['schemas']['HTTPValidationError']
        }
      }
      /** @description Internal Server Error */
      500: {
        headers: {
          [name: string]: unknown
        }
        content: {
          'application/json': components['schemas']['ErrorResponse']
        }
      }
    }
  }
  getChannelAvatar: {
    parameters: {
      query?: never
      header?: never
      path: {
        channel_id: string
      }
      cookie?: never
    }
    requestBody?: never
    responses: {
      /** @description Successful Response */
      200: {
        headers: {
          [name: string]: unknown
        }
        content?: never
      }
      /** @description Unauthorized */
      401: {
        headers: {
          [name: string]: unknown
        }
        content: {
          'application/json': components['schemas']['ErrorResponse']
        }
      }
      /** @description Forbidden */
      403: {
        headers: {
          [name: string]: unknown
        }
        content: {
          'application/json': components['schemas']['ErrorResponse']
        }
      }
      /** @description Validation Error */
      422: {
        headers: {
          [name: string]: unknown
        }
        content: {
          'application/json': components['schemas']['HTTPValidationError']
        }
      }
      /** @description Internal Server Error */
      500: {
        headers: {
          [name: string]: unknown
        }
        content: {
          'application/json': components['schemas']['ErrorResponse']
        }
      }
    }
  }
  checkChannel: {
    parameters: {
      query?: never
      header?: never
      path: {
        channel_id: string
      }
      cookie?: never
    }
    requestBody?: {
      content: {
        'application/json': components['schemas']['CheckRequest'] | null
      }
    }
    responses: {
      /** @description Successful Response */
      202: {
        headers: {
          [name: string]: unknown
        }
        content: {
          'application/json': components['schemas']['Channel']
        }
      }
      /** @description Unauthorized */
      401: {
        headers: {
          [name: string]: unknown
        }
        content: {
          'application/json': components['schemas']['ErrorResponse']
        }
      }
      /** @description Forbidden */
      403: {
        headers: {
          [name: string]: unknown
        }
        content: {
          'application/json': components['schemas']['ErrorResponse']
        }
      }
      /** @description Validation Error */
      422: {
        headers: {
          [name: string]: unknown
        }
        content: {
          'application/json': components['schemas']['HTTPValidationError']
        }
      }
      /** @description Internal Server Error */
      500: {
        headers: {
          [name: string]: unknown
        }
        content: {
          'application/json': components['schemas']['ErrorResponse']
        }
      }
    }
  }
  cancelCheck: {
    parameters: {
      query?: never
      header?: never
      path: {
        channel_id: string
      }
      cookie?: never
    }
    requestBody?: never
    responses: {
      /** @description Successful Response */
      200: {
        headers: {
          [name: string]: unknown
        }
        content: {
          'application/json': components['schemas']['CancelCheckResponse']
        }
      }
      /** @description Unauthorized */
      401: {
        headers: {
          [name: string]: unknown
        }
        content: {
          'application/json': components['schemas']['ErrorResponse']
        }
      }
      /** @description Forbidden */
      403: {
        headers: {
          [name: string]: unknown
        }
        content: {
          'application/json': components['schemas']['ErrorResponse']
        }
      }
      /** @description Validation Error */
      422: {
        headers: {
          [name: string]: unknown
        }
        content: {
          'application/json': components['schemas']['HTTPValidationError']
        }
      }
      /** @description Internal Server Error */
      500: {
        headers: {
          [name: string]: unknown
        }
        content: {
          'application/json': components['schemas']['ErrorResponse']
        }
      }
    }
  }
  getFilesToTrash: {
    parameters: {
      query?: never
      header?: never
      path: {
        channel_id: string
      }
      cookie?: never
    }
    requestBody?: never
    responses: {
      /** @description Successful Response */
      200: {
        headers: {
          [name: string]: unknown
        }
        content: {
          'application/json': components['schemas']['FilesToTrashResponse']
        }
      }
      /** @description Unauthorized */
      401: {
        headers: {
          [name: string]: unknown
        }
        content: {
          'application/json': components['schemas']['ErrorResponse']
        }
      }
      /** @description Forbidden */
      403: {
        headers: {
          [name: string]: unknown
        }
        content: {
          'application/json': components['schemas']['ErrorResponse']
        }
      }
      /** @description Validation Error */
      422: {
        headers: {
          [name: string]: unknown
        }
        content: {
          'application/json': components['schemas']['HTTPValidationError']
        }
      }
      /** @description Internal Server Error */
      500: {
        headers: {
          [name: string]: unknown
        }
        content: {
          'application/json': components['schemas']['ErrorResponse']
        }
      }
    }
  }
  mirrorMissing: {
    parameters: {
      query?: never
      header?: never
      path: {
        channel_id: string
      }
      cookie?: never
    }
    requestBody?: never
    responses: {
      /** @description Successful Response */
      202: {
        headers: {
          [name: string]: unknown
        }
        content: {
          'application/json': components['schemas']['MirrorResponse']
        }
      }
      /** @description Unauthorized */
      401: {
        headers: {
          [name: string]: unknown
        }
        content: {
          'application/json': components['schemas']['ErrorResponse']
        }
      }
      /** @description Forbidden */
      403: {
        headers: {
          [name: string]: unknown
        }
        content: {
          'application/json': components['schemas']['ErrorResponse']
        }
      }
      /** @description Validation Error */
      422: {
        headers: {
          [name: string]: unknown
        }
        content: {
          'application/json': components['schemas']['HTTPValidationError']
        }
      }
      /** @description Internal Server Error */
      500: {
        headers: {
          [name: string]: unknown
        }
        content: {
          'application/json': components['schemas']['ErrorResponse']
        }
      }
    }
  }
  leaveMissing: {
    parameters: {
      query?: never
      header?: never
      path: {
        channel_id: string
      }
      cookie?: never
    }
    requestBody?: never
    responses: {
      /** @description Successful Response */
      200: {
        headers: {
          [name: string]: unknown
        }
        content: {
          'application/json': components['schemas']['Channel']
        }
      }
      /** @description Unauthorized */
      401: {
        headers: {
          [name: string]: unknown
        }
        content: {
          'application/json': components['schemas']['ErrorResponse']
        }
      }
      /** @description Forbidden */
      403: {
        headers: {
          [name: string]: unknown
        }
        content: {
          'application/json': components['schemas']['ErrorResponse']
        }
      }
      /** @description Validation Error */
      422: {
        headers: {
          [name: string]: unknown
        }
        content: {
          'application/json': components['schemas']['HTTPValidationError']
        }
      }
      /** @description Internal Server Error */
      500: {
        headers: {
          [name: string]: unknown
        }
        content: {
          'application/json': components['schemas']['ErrorResponse']
        }
      }
    }
  }
  mirrorThemAgain: {
    parameters: {
      query?: never
      header?: never
      path: {
        channel_id: string
      }
      cookie?: never
    }
    requestBody?: never
    responses: {
      /** @description Successful Response */
      202: {
        headers: {
          [name: string]: unknown
        }
        content: {
          'application/json': components['schemas']['MirrorResponse']
        }
      }
      /** @description Unauthorized */
      401: {
        headers: {
          [name: string]: unknown
        }
        content: {
          'application/json': components['schemas']['ErrorResponse']
        }
      }
      /** @description Forbidden */
      403: {
        headers: {
          [name: string]: unknown
        }
        content: {
          'application/json': components['schemas']['ErrorResponse']
        }
      }
      /** @description Validation Error */
      422: {
        headers: {
          [name: string]: unknown
        }
        content: {
          'application/json': components['schemas']['HTTPValidationError']
        }
      }
      /** @description Internal Server Error */
      500: {
        headers: {
          [name: string]: unknown
        }
        content: {
          'application/json': components['schemas']['ErrorResponse']
        }
      }
    }
  }
  openChannelFolder: {
    parameters: {
      query?: never
      header?: never
      path: {
        channel_id: string
      }
      cookie?: never
    }
    requestBody?: never
    responses: {
      /** @description Successful Response */
      204: {
        headers: {
          [name: string]: unknown
        }
        content?: never
      }
      /** @description Unauthorized */
      401: {
        headers: {
          [name: string]: unknown
        }
        content: {
          'application/json': components['schemas']['ErrorResponse']
        }
      }
      /** @description Forbidden */
      403: {
        headers: {
          [name: string]: unknown
        }
        content: {
          'application/json': components['schemas']['ErrorResponse']
        }
      }
      /** @description Validation Error */
      422: {
        headers: {
          [name: string]: unknown
        }
        content: {
          'application/json': components['schemas']['HTTPValidationError']
        }
      }
      /** @description Internal Server Error */
      500: {
        headers: {
          [name: string]: unknown
        }
        content: {
          'application/json': components['schemas']['ErrorResponse']
        }
      }
    }
  }
  repairDates: {
    parameters: {
      query?: never
      header?: never
      path: {
        channel_id: string
      }
      cookie?: never
    }
    requestBody?: never
    responses: {
      /** @description Successful Response */
      200: {
        headers: {
          [name: string]: unknown
        }
        content: {
          'application/json': components['schemas']['RepairDatesResponse']
        }
      }
      /** @description Unauthorized */
      401: {
        headers: {
          [name: string]: unknown
        }
        content: {
          'application/json': components['schemas']['ErrorResponse']
        }
      }
      /** @description Forbidden */
      403: {
        headers: {
          [name: string]: unknown
        }
        content: {
          'application/json': components['schemas']['ErrorResponse']
        }
      }
      /** @description Validation Error */
      422: {
        headers: {
          [name: string]: unknown
        }
        content: {
          'application/json': components['schemas']['HTTPValidationError']
        }
      }
      /** @description Internal Server Error */
      500: {
        headers: {
          [name: string]: unknown
        }
        content: {
          'application/json': components['schemas']['ErrorResponse']
        }
      }
    }
  }
  getChannelVideos: {
    parameters: {
      query?: never
      header?: never
      path: {
        channel_id: string
      }
      cookie?: never
    }
    requestBody?: never
    responses: {
      /** @description Successful Response */
      200: {
        headers: {
          [name: string]: unknown
        }
        content: {
          'application/json': components['schemas']['VideosResponse']
        }
      }
      /** @description Unauthorized */
      401: {
        headers: {
          [name: string]: unknown
        }
        content: {
          'application/json': components['schemas']['ErrorResponse']
        }
      }
      /** @description Forbidden */
      403: {
        headers: {
          [name: string]: unknown
        }
        content: {
          'application/json': components['schemas']['ErrorResponse']
        }
      }
      /** @description Validation Error */
      422: {
        headers: {
          [name: string]: unknown
        }
        content: {
          'application/json': components['schemas']['HTTPValidationError']
        }
      }
      /** @description Internal Server Error */
      500: {
        headers: {
          [name: string]: unknown
        }
        content: {
          'application/json': components['schemas']['ErrorResponse']
        }
      }
    }
  }
  getEvents: {
    parameters: {
      query?: never
      header?: never
      path?: never
      cookie?: never
    }
    requestBody?: never
    responses: {
      /** @description A stream of Server-Sent Events. The events ``tool.updated``, ``channel.updated``, ``task.progress``, ``banner.changed``, ``video.updated``, ``videos.changed``, ``job.progress``, ``apikey.changed``, ``checks.progress``, ``queue.updated``, ``menu.command`` and ``quit.asked`` carry these data, in this order. */
      200: {
        headers: {
          [name: string]: unknown
        }
        content: {
          'application/json': components['schemas']['EventData']
        }
      }
      /** @description Unauthorized */
      401: {
        headers: {
          [name: string]: unknown
        }
        content: {
          'application/json': components['schemas']['ErrorResponse']
        }
      }
      /** @description Forbidden */
      403: {
        headers: {
          [name: string]: unknown
        }
        content: {
          'application/json': components['schemas']['ErrorResponse']
        }
      }
      /** @description Internal Server Error */
      500: {
        headers: {
          [name: string]: unknown
        }
        content: {
          'application/json': components['schemas']['ErrorResponse']
        }
      }
    }
  }
  chooseFolder: {
    parameters: {
      query?: never
      header?: never
      path?: never
      cookie?: never
    }
    requestBody?: never
    responses: {
      /** @description Successful Response */
      200: {
        headers: {
          [name: string]: unknown
        }
        content: {
          'application/json': components['schemas']['ChosenFolderResponse']
        }
      }
      /** @description Unauthorized */
      401: {
        headers: {
          [name: string]: unknown
        }
        content: {
          'application/json': components['schemas']['ErrorResponse']
        }
      }
      /** @description Forbidden */
      403: {
        headers: {
          [name: string]: unknown
        }
        content: {
          'application/json': components['schemas']['ErrorResponse']
        }
      }
      /** @description Internal Server Error */
      500: {
        headers: {
          [name: string]: unknown
        }
        content: {
          'application/json': components['schemas']['ErrorResponse']
        }
      }
    }
  }
  getHealth: {
    parameters: {
      query?: never
      header?: never
      path?: never
      cookie?: never
    }
    requestBody?: never
    responses: {
      /** @description Successful Response */
      200: {
        headers: {
          [name: string]: unknown
        }
        content: {
          'application/json': components['schemas']['HealthResponse']
        }
      }
      /** @description Unauthorized */
      401: {
        headers: {
          [name: string]: unknown
        }
        content: {
          'application/json': components['schemas']['ErrorResponse']
        }
      }
      /** @description Forbidden */
      403: {
        headers: {
          [name: string]: unknown
        }
        content: {
          'application/json': components['schemas']['ErrorResponse']
        }
      }
      /** @description Internal Server Error */
      500: {
        headers: {
          [name: string]: unknown
        }
        content: {
          'application/json': components['schemas']['ErrorResponse']
        }
      }
    }
  }
  cancelJob: {
    parameters: {
      query?: never
      header?: never
      path: {
        job_id: string
      }
      cookie?: never
    }
    requestBody?: never
    responses: {
      /** @description Successful Response */
      200: {
        headers: {
          [name: string]: unknown
        }
        content: {
          'application/json': components['schemas']['CancelJobResponse']
        }
      }
      /** @description Unauthorized */
      401: {
        headers: {
          [name: string]: unknown
        }
        content: {
          'application/json': components['schemas']['ErrorResponse']
        }
      }
      /** @description Forbidden */
      403: {
        headers: {
          [name: string]: unknown
        }
        content: {
          'application/json': components['schemas']['ErrorResponse']
        }
      }
      /** @description Validation Error */
      422: {
        headers: {
          [name: string]: unknown
        }
        content: {
          'application/json': components['schemas']['HTTPValidationError']
        }
      }
      /** @description Internal Server Error */
      500: {
        headers: {
          [name: string]: unknown
        }
        content: {
          'application/json': components['schemas']['ErrorResponse']
        }
      }
    }
  }
  getQueue: {
    parameters: {
      query?: never
      header?: never
      path?: never
      cookie?: never
    }
    requestBody?: never
    responses: {
      /** @description Successful Response */
      200: {
        headers: {
          [name: string]: unknown
        }
        content: {
          'application/json': components['schemas']['QueueResponse']
        }
      }
      /** @description Unauthorized */
      401: {
        headers: {
          [name: string]: unknown
        }
        content: {
          'application/json': components['schemas']['ErrorResponse']
        }
      }
      /** @description Forbidden */
      403: {
        headers: {
          [name: string]: unknown
        }
        content: {
          'application/json': components['schemas']['ErrorResponse']
        }
      }
      /** @description Internal Server Error */
      500: {
        headers: {
          [name: string]: unknown
        }
        content: {
          'application/json': components['schemas']['ErrorResponse']
        }
      }
    }
  }
  clearWaiting: {
    parameters: {
      query?: never
      header?: never
      path?: never
      cookie?: never
    }
    requestBody?: never
    responses: {
      /** @description Successful Response */
      200: {
        headers: {
          [name: string]: unknown
        }
        content: {
          'application/json': components['schemas']['ClearWaitingResponse']
        }
      }
      /** @description Unauthorized */
      401: {
        headers: {
          [name: string]: unknown
        }
        content: {
          'application/json': components['schemas']['ErrorResponse']
        }
      }
      /** @description Forbidden */
      403: {
        headers: {
          [name: string]: unknown
        }
        content: {
          'application/json': components['schemas']['ErrorResponse']
        }
      }
      /** @description Internal Server Error */
      500: {
        headers: {
          [name: string]: unknown
        }
        content: {
          'application/json': components['schemas']['ErrorResponse']
        }
      }
    }
  }
  tryFolderAgain: {
    parameters: {
      query?: never
      header?: never
      path: {
        channel_id: string
      }
      cookie?: never
    }
    requestBody?: never
    responses: {
      /** @description Successful Response */
      200: {
        headers: {
          [name: string]: unknown
        }
        content: {
          'application/json': components['schemas']['TryFolderResponse']
        }
      }
      /** @description Unauthorized */
      401: {
        headers: {
          [name: string]: unknown
        }
        content: {
          'application/json': components['schemas']['ErrorResponse']
        }
      }
      /** @description Forbidden */
      403: {
        headers: {
          [name: string]: unknown
        }
        content: {
          'application/json': components['schemas']['ErrorResponse']
        }
      }
      /** @description Validation Error */
      422: {
        headers: {
          [name: string]: unknown
        }
        content: {
          'application/json': components['schemas']['HTTPValidationError']
        }
      }
      /** @description Internal Server Error */
      500: {
        headers: {
          [name: string]: unknown
        }
        content: {
          'application/json': components['schemas']['ErrorResponse']
        }
      }
    }
  }
  pauseQueue: {
    parameters: {
      query?: never
      header?: never
      path?: never
      cookie?: never
    }
    requestBody?: never
    responses: {
      /** @description Successful Response */
      200: {
        headers: {
          [name: string]: unknown
        }
        content: {
          'application/json': components['schemas']['Queue']
        }
      }
      /** @description Unauthorized */
      401: {
        headers: {
          [name: string]: unknown
        }
        content: {
          'application/json': components['schemas']['ErrorResponse']
        }
      }
      /** @description Forbidden */
      403: {
        headers: {
          [name: string]: unknown
        }
        content: {
          'application/json': components['schemas']['ErrorResponse']
        }
      }
      /** @description Internal Server Error */
      500: {
        headers: {
          [name: string]: unknown
        }
        content: {
          'application/json': components['schemas']['ErrorResponse']
        }
      }
    }
  }
  reorderQueue: {
    parameters: {
      query?: never
      header?: never
      path?: never
      cookie?: never
    }
    requestBody: {
      content: {
        'application/json': components['schemas']['ReorderRequest']
      }
    }
    responses: {
      /** @description Successful Response */
      204: {
        headers: {
          [name: string]: unknown
        }
        content?: never
      }
      /** @description Unauthorized */
      401: {
        headers: {
          [name: string]: unknown
        }
        content: {
          'application/json': components['schemas']['ErrorResponse']
        }
      }
      /** @description Forbidden */
      403: {
        headers: {
          [name: string]: unknown
        }
        content: {
          'application/json': components['schemas']['ErrorResponse']
        }
      }
      /** @description Validation Error */
      422: {
        headers: {
          [name: string]: unknown
        }
        content: {
          'application/json': components['schemas']['HTTPValidationError']
        }
      }
      /** @description Internal Server Error */
      500: {
        headers: {
          [name: string]: unknown
        }
        content: {
          'application/json': components['schemas']['ErrorResponse']
        }
      }
    }
  }
  resumeQueue: {
    parameters: {
      query?: never
      header?: never
      path?: never
      cookie?: never
    }
    requestBody?: never
    responses: {
      /** @description Successful Response */
      200: {
        headers: {
          [name: string]: unknown
        }
        content: {
          'application/json': components['schemas']['Queue']
        }
      }
      /** @description Unauthorized */
      401: {
        headers: {
          [name: string]: unknown
        }
        content: {
          'application/json': components['schemas']['ErrorResponse']
        }
      }
      /** @description Forbidden */
      403: {
        headers: {
          [name: string]: unknown
        }
        content: {
          'application/json': components['schemas']['ErrorResponse']
        }
      }
      /** @description Internal Server Error */
      500: {
        headers: {
          [name: string]: unknown
        }
        content: {
          'application/json': components['schemas']['ErrorResponse']
        }
      }
    }
  }
  resumeAnyway: {
    parameters: {
      query?: never
      header?: never
      path?: never
      cookie?: never
    }
    requestBody?: never
    responses: {
      /** @description Successful Response */
      200: {
        headers: {
          [name: string]: unknown
        }
        content: {
          'application/json': components['schemas']['Queue']
        }
      }
      /** @description Unauthorized */
      401: {
        headers: {
          [name: string]: unknown
        }
        content: {
          'application/json': components['schemas']['ErrorResponse']
        }
      }
      /** @description Forbidden */
      403: {
        headers: {
          [name: string]: unknown
        }
        content: {
          'application/json': components['schemas']['ErrorResponse']
        }
      }
      /** @description Internal Server Error */
      500: {
        headers: {
          [name: string]: unknown
        }
        content: {
          'application/json': components['schemas']['ErrorResponse']
        }
      }
    }
  }
  setSpeedLimit: {
    parameters: {
      query?: never
      header?: never
      path?: never
      cookie?: never
    }
    requestBody: {
      content: {
        'application/json': components['schemas']['SpeedLimitRequest']
      }
    }
    responses: {
      /** @description Successful Response */
      200: {
        headers: {
          [name: string]: unknown
        }
        content: {
          'application/json': components['schemas']['Queue']
        }
      }
      /** @description Unauthorized */
      401: {
        headers: {
          [name: string]: unknown
        }
        content: {
          'application/json': components['schemas']['ErrorResponse']
        }
      }
      /** @description Forbidden */
      403: {
        headers: {
          [name: string]: unknown
        }
        content: {
          'application/json': components['schemas']['ErrorResponse']
        }
      }
      /** @description Validation Error */
      422: {
        headers: {
          [name: string]: unknown
        }
        content: {
          'application/json': components['schemas']['HTTPValidationError']
        }
      }
      /** @description Internal Server Error */
      500: {
        headers: {
          [name: string]: unknown
        }
        content: {
          'application/json': components['schemas']['ErrorResponse']
        }
      }
    }
  }
  getApiKey: {
    parameters: {
      query?: never
      header?: never
      path?: never
      cookie?: never
    }
    requestBody?: never
    responses: {
      /** @description Successful Response */
      200: {
        headers: {
          [name: string]: unknown
        }
        content: {
          'application/json': components['schemas']['ApiKey']
        }
      }
      /** @description Unauthorized */
      401: {
        headers: {
          [name: string]: unknown
        }
        content: {
          'application/json': components['schemas']['ErrorResponse']
        }
      }
      /** @description Forbidden */
      403: {
        headers: {
          [name: string]: unknown
        }
        content: {
          'application/json': components['schemas']['ErrorResponse']
        }
      }
      /** @description Internal Server Error */
      500: {
        headers: {
          [name: string]: unknown
        }
        content: {
          'application/json': components['schemas']['ErrorResponse']
        }
      }
    }
  }
  saveApiKey: {
    parameters: {
      query?: never
      header?: never
      path?: never
      cookie?: never
    }
    requestBody: {
      content: {
        'application/json': components['schemas']['SaveApiKeyRequest']
      }
    }
    responses: {
      /** @description Successful Response */
      200: {
        headers: {
          [name: string]: unknown
        }
        content: {
          'application/json': components['schemas']['ApiKey']
        }
      }
      /** @description Unauthorized */
      401: {
        headers: {
          [name: string]: unknown
        }
        content: {
          'application/json': components['schemas']['ErrorResponse']
        }
      }
      /** @description Forbidden */
      403: {
        headers: {
          [name: string]: unknown
        }
        content: {
          'application/json': components['schemas']['ErrorResponse']
        }
      }
      /** @description Validation Error */
      422: {
        headers: {
          [name: string]: unknown
        }
        content: {
          'application/json': components['schemas']['HTTPValidationError']
        }
      }
      /** @description Internal Server Error */
      500: {
        headers: {
          [name: string]: unknown
        }
        content: {
          'application/json': components['schemas']['ErrorResponse']
        }
      }
    }
  }
  removeApiKey: {
    parameters: {
      query?: never
      header?: never
      path?: never
      cookie?: never
    }
    requestBody?: never
    responses: {
      /** @description Successful Response */
      200: {
        headers: {
          [name: string]: unknown
        }
        content: {
          'application/json': components['schemas']['ApiKey']
        }
      }
      /** @description Unauthorized */
      401: {
        headers: {
          [name: string]: unknown
        }
        content: {
          'application/json': components['schemas']['ErrorResponse']
        }
      }
      /** @description Forbidden */
      403: {
        headers: {
          [name: string]: unknown
        }
        content: {
          'application/json': components['schemas']['ErrorResponse']
        }
      }
      /** @description Internal Server Error */
      500: {
        headers: {
          [name: string]: unknown
        }
        content: {
          'application/json': components['schemas']['ErrorResponse']
        }
      }
    }
  }
  testApiKey: {
    parameters: {
      query?: never
      header?: never
      path?: never
      cookie?: never
    }
    requestBody: {
      content: {
        'application/json': components['schemas']['TestApiKeyRequest']
      }
    }
    responses: {
      /** @description Successful Response */
      200: {
        headers: {
          [name: string]: unknown
        }
        content: {
          'application/json': components['schemas']['TestApiKeyResponse']
        }
      }
      /** @description Unauthorized */
      401: {
        headers: {
          [name: string]: unknown
        }
        content: {
          'application/json': components['schemas']['ErrorResponse']
        }
      }
      /** @description Forbidden */
      403: {
        headers: {
          [name: string]: unknown
        }
        content: {
          'application/json': components['schemas']['ErrorResponse']
        }
      }
      /** @description Validation Error */
      422: {
        headers: {
          [name: string]: unknown
        }
        content: {
          'application/json': components['schemas']['HTTPValidationError']
        }
      }
      /** @description Internal Server Error */
      500: {
        headers: {
          [name: string]: unknown
        }
        content: {
          'application/json': components['schemas']['ErrorResponse']
        }
      }
    }
  }
  getState: {
    parameters: {
      query?: never
      header?: never
      path?: never
      cookie?: never
    }
    requestBody?: never
    responses: {
      /** @description Successful Response */
      200: {
        headers: {
          [name: string]: unknown
        }
        content: {
          'application/json': components['schemas']['StateResponse']
        }
      }
      /** @description Unauthorized */
      401: {
        headers: {
          [name: string]: unknown
        }
        content: {
          'application/json': components['schemas']['ErrorResponse']
        }
      }
      /** @description Forbidden */
      403: {
        headers: {
          [name: string]: unknown
        }
        content: {
          'application/json': components['schemas']['ErrorResponse']
        }
      }
      /** @description Internal Server Error */
      500: {
        headers: {
          [name: string]: unknown
        }
        content: {
          'application/json': components['schemas']['ErrorResponse']
        }
      }
    }
  }
  setOpenChannel: {
    parameters: {
      query?: never
      header?: never
      path?: never
      cookie?: never
    }
    requestBody: {
      content: {
        'application/json': components['schemas']['OpenChannelRequest']
      }
    }
    responses: {
      /** @description Successful Response */
      200: {
        headers: {
          [name: string]: unknown
        }
        content: {
          'application/json': components['schemas']['StateResponse']
        }
      }
      /** @description Unauthorized */
      401: {
        headers: {
          [name: string]: unknown
        }
        content: {
          'application/json': components['schemas']['ErrorResponse']
        }
      }
      /** @description Forbidden */
      403: {
        headers: {
          [name: string]: unknown
        }
        content: {
          'application/json': components['schemas']['ErrorResponse']
        }
      }
      /** @description Validation Error */
      422: {
        headers: {
          [name: string]: unknown
        }
        content: {
          'application/json': components['schemas']['HTTPValidationError']
        }
      }
      /** @description Internal Server Error */
      500: {
        headers: {
          [name: string]: unknown
        }
        content: {
          'application/json': components['schemas']['ErrorResponse']
        }
      }
    }
  }
  setView: {
    parameters: {
      query?: never
      header?: never
      path?: never
      cookie?: never
    }
    requestBody: {
      content: {
        'application/json': components['schemas']['ViewRequest']
      }
    }
    responses: {
      /** @description Successful Response */
      200: {
        headers: {
          [name: string]: unknown
        }
        content: {
          'application/json': components['schemas']['StateResponse']
        }
      }
      /** @description Unauthorized */
      401: {
        headers: {
          [name: string]: unknown
        }
        content: {
          'application/json': components['schemas']['ErrorResponse']
        }
      }
      /** @description Forbidden */
      403: {
        headers: {
          [name: string]: unknown
        }
        content: {
          'application/json': components['schemas']['ErrorResponse']
        }
      }
      /** @description Validation Error */
      422: {
        headers: {
          [name: string]: unknown
        }
        content: {
          'application/json': components['schemas']['HTTPValidationError']
        }
      }
      /** @description Internal Server Error */
      500: {
        headers: {
          [name: string]: unknown
        }
        content: {
          'application/json': components['schemas']['ErrorResponse']
        }
      }
    }
  }
  getTools: {
    parameters: {
      query?: never
      header?: never
      path?: never
      cookie?: never
    }
    requestBody?: never
    responses: {
      /** @description Successful Response */
      200: {
        headers: {
          [name: string]: unknown
        }
        content: {
          'application/json': components['schemas']['ToolsResponse']
        }
      }
      /** @description Unauthorized */
      401: {
        headers: {
          [name: string]: unknown
        }
        content: {
          'application/json': components['schemas']['ErrorResponse']
        }
      }
      /** @description Forbidden */
      403: {
        headers: {
          [name: string]: unknown
        }
        content: {
          'application/json': components['schemas']['ErrorResponse']
        }
      }
      /** @description Internal Server Error */
      500: {
        headers: {
          [name: string]: unknown
        }
        content: {
          'application/json': components['schemas']['ErrorResponse']
        }
      }
    }
  }
  installTool: {
    parameters: {
      query?: never
      header?: never
      path: {
        name: components['schemas']['ToolName']
      }
      cookie?: never
    }
    requestBody?: never
    responses: {
      /** @description Successful Response */
      202: {
        headers: {
          [name: string]: unknown
        }
        content: {
          'application/json': components['schemas']['Tool']
        }
      }
      /** @description Unauthorized */
      401: {
        headers: {
          [name: string]: unknown
        }
        content: {
          'application/json': components['schemas']['ErrorResponse']
        }
      }
      /** @description Forbidden */
      403: {
        headers: {
          [name: string]: unknown
        }
        content: {
          'application/json': components['schemas']['ErrorResponse']
        }
      }
      /** @description Validation Error */
      422: {
        headers: {
          [name: string]: unknown
        }
        content: {
          'application/json': components['schemas']['HTTPValidationError']
        }
      }
      /** @description Internal Server Error */
      500: {
        headers: {
          [name: string]: unknown
        }
        content: {
          'application/json': components['schemas']['ErrorResponse']
        }
      }
    }
  }
  confirmQuit: {
    parameters: {
      query?: never
      header?: never
      path?: never
      cookie?: never
    }
    requestBody?: never
    responses: {
      /** @description Successful Response */
      204: {
        headers: {
          [name: string]: unknown
        }
        content?: never
      }
      /** @description Unauthorized */
      401: {
        headers: {
          [name: string]: unknown
        }
        content: {
          'application/json': components['schemas']['ErrorResponse']
        }
      }
      /** @description Forbidden */
      403: {
        headers: {
          [name: string]: unknown
        }
        content: {
          'application/json': components['schemas']['ErrorResponse']
        }
      }
      /** @description Internal Server Error */
      500: {
        headers: {
          [name: string]: unknown
        }
        content: {
          'application/json': components['schemas']['ErrorResponse']
        }
      }
    }
  }
  reportUiState: {
    parameters: {
      query?: never
      header?: never
      path?: never
      cookie?: never
    }
    requestBody: {
      content: {
        'application/json': components['schemas']['UiStateRequest']
      }
    }
    responses: {
      /** @description Successful Response */
      204: {
        headers: {
          [name: string]: unknown
        }
        content?: never
      }
      /** @description Unauthorized */
      401: {
        headers: {
          [name: string]: unknown
        }
        content: {
          'application/json': components['schemas']['ErrorResponse']
        }
      }
      /** @description Forbidden */
      403: {
        headers: {
          [name: string]: unknown
        }
        content: {
          'application/json': components['schemas']['ErrorResponse']
        }
      }
      /** @description Validation Error */
      422: {
        headers: {
          [name: string]: unknown
        }
        content: {
          'application/json': components['schemas']['HTTPValidationError']
        }
      }
      /** @description Internal Server Error */
      500: {
        headers: {
          [name: string]: unknown
        }
        content: {
          'application/json': components['schemas']['ErrorResponse']
        }
      }
    }
  }
  mirrorVideos: {
    parameters: {
      query?: never
      header?: never
      path?: never
      cookie?: never
    }
    requestBody: {
      content: {
        'application/json': components['schemas']['MirrorRequest']
      }
    }
    responses: {
      /** @description Successful Response */
      202: {
        headers: {
          [name: string]: unknown
        }
        content: {
          'application/json': components['schemas']['MirrorResponse']
        }
      }
      /** @description Unauthorized */
      401: {
        headers: {
          [name: string]: unknown
        }
        content: {
          'application/json': components['schemas']['ErrorResponse']
        }
      }
      /** @description Forbidden */
      403: {
        headers: {
          [name: string]: unknown
        }
        content: {
          'application/json': components['schemas']['ErrorResponse']
        }
      }
      /** @description Validation Error */
      422: {
        headers: {
          [name: string]: unknown
        }
        content: {
          'application/json': components['schemas']['HTTPValidationError']
        }
      }
      /** @description Internal Server Error */
      500: {
        headers: {
          [name: string]: unknown
        }
        content: {
          'application/json': components['schemas']['ErrorResponse']
        }
      }
    }
  }
  redownloadVideos: {
    parameters: {
      query?: never
      header?: never
      path?: never
      cookie?: never
    }
    requestBody: {
      content: {
        'application/json': components['schemas']['MirrorRequest']
      }
    }
    responses: {
      /** @description Successful Response */
      202: {
        headers: {
          [name: string]: unknown
        }
        content: {
          'application/json': components['schemas']['MirrorResponse']
        }
      }
      /** @description Unauthorized */
      401: {
        headers: {
          [name: string]: unknown
        }
        content: {
          'application/json': components['schemas']['ErrorResponse']
        }
      }
      /** @description Forbidden */
      403: {
        headers: {
          [name: string]: unknown
        }
        content: {
          'application/json': components['schemas']['ErrorResponse']
        }
      }
      /** @description Validation Error */
      422: {
        headers: {
          [name: string]: unknown
        }
        content: {
          'application/json': components['schemas']['HTTPValidationError']
        }
      }
      /** @description Internal Server Error */
      500: {
        headers: {
          [name: string]: unknown
        }
        content: {
          'application/json': components['schemas']['ErrorResponse']
        }
      }
    }
  }
  getVideo: {
    parameters: {
      query?: never
      header?: never
      path: {
        video_id: string
      }
      cookie?: never
    }
    requestBody?: never
    responses: {
      /** @description Successful Response */
      200: {
        headers: {
          [name: string]: unknown
        }
        content: {
          'application/json': components['schemas']['VideoDetailsResponse']
        }
      }
      /** @description Unauthorized */
      401: {
        headers: {
          [name: string]: unknown
        }
        content: {
          'application/json': components['schemas']['ErrorResponse']
        }
      }
      /** @description Forbidden */
      403: {
        headers: {
          [name: string]: unknown
        }
        content: {
          'application/json': components['schemas']['ErrorResponse']
        }
      }
      /** @description Validation Error */
      422: {
        headers: {
          [name: string]: unknown
        }
        content: {
          'application/json': components['schemas']['HTTPValidationError']
        }
      }
      /** @description Internal Server Error */
      500: {
        headers: {
          [name: string]: unknown
        }
        content: {
          'application/json': components['schemas']['ErrorResponse']
        }
      }
    }
  }
  playVideo: {
    parameters: {
      query?: never
      header?: never
      path: {
        video_id: string
      }
      cookie?: never
    }
    requestBody?: never
    responses: {
      /** @description Successful Response */
      204: {
        headers: {
          [name: string]: unknown
        }
        content?: never
      }
      /** @description Unauthorized */
      401: {
        headers: {
          [name: string]: unknown
        }
        content: {
          'application/json': components['schemas']['ErrorResponse']
        }
      }
      /** @description Forbidden */
      403: {
        headers: {
          [name: string]: unknown
        }
        content: {
          'application/json': components['schemas']['ErrorResponse']
        }
      }
      /** @description Validation Error */
      422: {
        headers: {
          [name: string]: unknown
        }
        content: {
          'application/json': components['schemas']['HTTPValidationError']
        }
      }
      /** @description Internal Server Error */
      500: {
        headers: {
          [name: string]: unknown
        }
        content: {
          'application/json': components['schemas']['ErrorResponse']
        }
      }
    }
  }
  retryVideo: {
    parameters: {
      query?: never
      header?: never
      path: {
        video_id: string
      }
      cookie?: never
    }
    requestBody?: never
    responses: {
      /** @description Successful Response */
      202: {
        headers: {
          [name: string]: unknown
        }
        content: {
          'application/json': components['schemas']['Video']
        }
      }
      /** @description Unauthorized */
      401: {
        headers: {
          [name: string]: unknown
        }
        content: {
          'application/json': components['schemas']['ErrorResponse']
        }
      }
      /** @description Forbidden */
      403: {
        headers: {
          [name: string]: unknown
        }
        content: {
          'application/json': components['schemas']['ErrorResponse']
        }
      }
      /** @description Validation Error */
      422: {
        headers: {
          [name: string]: unknown
        }
        content: {
          'application/json': components['schemas']['HTTPValidationError']
        }
      }
      /** @description Internal Server Error */
      500: {
        headers: {
          [name: string]: unknown
        }
        content: {
          'application/json': components['schemas']['ErrorResponse']
        }
      }
    }
  }
  revealVideo: {
    parameters: {
      query?: never
      header?: never
      path: {
        video_id: string
      }
      cookie?: never
    }
    requestBody?: never
    responses: {
      /** @description Successful Response */
      204: {
        headers: {
          [name: string]: unknown
        }
        content?: never
      }
      /** @description Unauthorized */
      401: {
        headers: {
          [name: string]: unknown
        }
        content: {
          'application/json': components['schemas']['ErrorResponse']
        }
      }
      /** @description Forbidden */
      403: {
        headers: {
          [name: string]: unknown
        }
        content: {
          'application/json': components['schemas']['ErrorResponse']
        }
      }
      /** @description Validation Error */
      422: {
        headers: {
          [name: string]: unknown
        }
        content: {
          'application/json': components['schemas']['HTTPValidationError']
        }
      }
      /** @description Internal Server Error */
      500: {
        headers: {
          [name: string]: unknown
        }
        content: {
          'application/json': components['schemas']['ErrorResponse']
        }
      }
    }
  }
  getVideoThumbnail: {
    parameters: {
      query?: never
      header?: never
      path: {
        video_id: string
      }
      cookie?: never
    }
    requestBody?: never
    responses: {
      /** @description Successful Response */
      200: {
        headers: {
          [name: string]: unknown
        }
        content?: never
      }
      /** @description Unauthorized */
      401: {
        headers: {
          [name: string]: unknown
        }
        content: {
          'application/json': components['schemas']['ErrorResponse']
        }
      }
      /** @description Forbidden */
      403: {
        headers: {
          [name: string]: unknown
        }
        content: {
          'application/json': components['schemas']['ErrorResponse']
        }
      }
      /** @description Validation Error */
      422: {
        headers: {
          [name: string]: unknown
        }
        content: {
          'application/json': components['schemas']['HTTPValidationError']
        }
      }
      /** @description Internal Server Error */
      500: {
        headers: {
          [name: string]: unknown
        }
        content: {
          'application/json': components['schemas']['ErrorResponse']
        }
      }
    }
  }
  tryYouTubeNow: {
    parameters: {
      query?: never
      header?: never
      path?: never
      cookie?: never
    }
    requestBody?: never
    responses: {
      /** @description Successful Response */
      200: {
        headers: {
          [name: string]: unknown
        }
        content: {
          'application/json': components['schemas']['StateResponse']
        }
      }
      /** @description Unauthorized */
      401: {
        headers: {
          [name: string]: unknown
        }
        content: {
          'application/json': components['schemas']['ErrorResponse']
        }
      }
      /** @description Forbidden */
      403: {
        headers: {
          [name: string]: unknown
        }
        content: {
          'application/json': components['schemas']['ErrorResponse']
        }
      }
      /** @description Internal Server Error */
      500: {
        headers: {
          [name: string]: unknown
        }
        content: {
          'application/json': components['schemas']['ErrorResponse']
        }
      }
    }
  }
}

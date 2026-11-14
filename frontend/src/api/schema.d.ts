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
     * @description Remove a channel with its catalogue. Its folder and files stay (R-CH-32).
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
     *         progress: The first listing or full check that is running, or None.
     *         pictures: A number that grows when more pictures of the channel are cached.
     *         avatar_version: A number that grows when the avatar of the channel was cached anew.
     *         catalogue_version: A number that grows with every successful check of the channel.
     */
    Channel: {
      /** Auto Mirror */
      auto_mirror: boolean
      /** Avatar Version */
      avatar_version: number
      /** Catalogue Version */
      catalogue_version: number
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
      /** Last Check At */
      last_check_at: number | null
      last_check_error: components['schemas']['ErrorCode'] | null
      /** Last Full Check At */
      last_full_check_at: number | null
      /** Mirror After */
      mirror_after: number | null
      /** New Videos */
      new_videos: number
      /** Paused */
      paused: boolean
      /** Pictures */
      pictures: number
      progress: components['schemas']['Progress'] | null
      quality: components['schemas']['Quality'] | null
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
    }
    /**
     * ChannelStatus
     * @description The one status line of a channel (R-FB-01). Derived, never stored.
     *
     *     Each milestone adds the statuses that can occur from it on.
     * @enum {string}
     */
    ChannelStatus: 'could_not_check' | 'checking' | 'new_videos' | 'paused' | 'up_to_date'
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
     */
    CheckRequest: {
      /** @default quick */
      kind: components['schemas']['CheckKind']
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
     * DatePrecision
     * @description The unit YouTube gave an approximate date in (R-DT-04, docs/GLOSSARY.md).
     * @enum {string}
     */
    DatePrecision: 'day' | 'week' | 'month' | 'year'
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
     * @description The quality a channel asks for (R-QL-01). The rules that use it arrive in milestone M3.
     * @enum {string}
     */
    Quality: 'best' | '2160' | '1440' | '1080' | '720' | '480'
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
     */
    StateResponse: {
      /** Can Choose Folder */
      can_choose_folder: boolean
      /** Channels */
      channels: components['schemas']['Channel'][]
      disk: components['schemas']['DiskSpace']
      /** Library Folder */
      library_folder: string
      /** Open Channel Id */
      open_channel_id: string | null
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
     */
    Video: {
      /** Duration S */
      duration_s: number | null
      /** Excluded */
      excluded: boolean
      /** Gone */
      gone: boolean
      /** Id */
      id: string
      /** Is New */
      is_new: boolean
      /** Published Around */
      published_around: number | null
      /** Published At */
      published_at: number | null
      published_precision: components['schemas']['DatePrecision'] | null
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
      /** @description A stream of Server-Sent Events. The events ``tool.updated``, ``channel.updated``, ``task.progress`` and ``banner.changed`` carry these data, in this order. */
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

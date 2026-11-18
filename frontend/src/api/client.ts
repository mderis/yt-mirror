/**
 * The thin typed client of the yt-mirror API (docs/ARCHITECTURE.md section 8).
 *
 * This is the only module that calls fetch. Stores use it, components never
 * do. The types come from schema.d.ts, which is generated from the OpenAPI
 * schema with `npm run gen:api` and never edited by hand.
 *
 * The session cookie set by the first URL travels with every request
 * (docs/DECISIONS.md D-038), so no token appears in this code.
 */
import type { components } from './schema'

export type Health = components['schemas']['HealthResponse']
/** The state of one tool the app needs (R-IN-03). */
export type Tool = components['schemas']['Tool']
export type ToolName = components['schemas']['ToolName']
export type ToolsAnswer = components['schemas']['ToolsResponse']
export type ToolUpdated = components['schemas']['ToolUpdatedEvent']
/** The app as the window draws it: the answer of `/api/state`. */
export type AppState = components['schemas']['StateResponse']
/** One channel with its status and its totals (R-CH-34, R-CH-35). */
export type Channel = components['schemas']['Channel']
export type ChannelStatus = components['schemas']['ChannelStatus']
/** One video of a catalogue, with the fields a list needs (R-CH-10). */
export type Video = components['schemas']['Video']
export type KeptFile = components['schemas']['KeptFileResponse']
export type VideoStatus = components['schemas']['VideoStatus']
/** How far the running download of a video is (R-QU-04). */
export type Download = components['schemas']['Download']
/** Everything the details panel shows of a video (R-UI-08). */
export type VideoDetails = components['schemas']['VideoDetailsResponse']
/** A download that was put in line (R-MI-01). */
export type QueuedJob = components['schemas']['QueuedJob']
/** What "Delete the files" moves to the Trash (R-CH-32). */
export type FilesToTrash = components['schemas']['FilesToTrashResponse']
export type RemovedChannel = components['schemas']['RemovedChannelResponse']
export type DatePrecision = components['schemas']['DatePrecision']
export type CheckKind = components['schemas']['CheckKind']
/** What the user pressed to start a check, logged with it. */
export type CheckTrigger = components['schemas']['CheckTrigger']
export type Quality = components['schemas']['Quality']
/** How far a first listing or a full check has come. */
export type Progress = components['schemas']['Progress']
/** The pause of what the app asks of YouTube by itself (R-ER-05). */
export type Pause = components['schemas']['Pause']
/** The preview of a channel before it is added (R-CH-03). */
export type ChannelLookup = components['schemas']['LookupResponse']
export type ChosenFolder = components['schemas']['ChosenFolderResponse']
export type NewChannel = components['schemas']['AddChannelRequest']
export type AddedChannel = components['schemas']['AddChannelResponse']
/** Every error code the app knows, from backend/ytmirror/core/errors.py through the API schema. */
export type ErrorCode = components['schemas']['ErrorCode']
export type ApiKey = components['schemas']['ApiKey']
export type ApiKeyTest = components['schemas']['TestApiKeyResponse']
export type DateInfo = components['schemas']['DateInfo']
export type ExactDates = components['schemas']['ExactDates']
export type RepairedDates = components['schemas']['RepairDatesResponse']
export type Counted = components['schemas']['Mirroring']
/** How the queue of downloads stands (R-QU-01, R-QU-02). */
export type Queue = components['schemas']['Queue']
/** The whole queue, as the downloads panel shows it. */
export type QueueAnswer = components['schemas']['QueueResponse']
export type QueueItem = components['schemas']['QueueItem']
export type FailedItem = components['schemas']['FailedItem']
/** The answer to the question before a large start of auto-mirror (D-095). */
export type AutoMirrorAnswer = components['schemas']['AutoMirrorAnswer']
/** List or grid (R-UI-03). */
export type ViewKind = components['schemas']['ViewKind']
type ErrorResponse = components['schemas']['ErrorResponse']

const API_PREFIX = '/api'
const UNREADABLE: ErrorCode = 'INTERNAL'
const NO_CONTENT = 204
/** The one code the window raises itself: its own server did not answer at all (R-ER-04). */
const UNREACHABLE: ErrorCode = 'LOCAL_SERVER_UNREACHABLE'

/** A failed API call, with the stable error code of docs/LOGGING.md section 4. */
export class ApiError extends Error {
  /** The HTTP status, or 0 when the server could not be reached. */
  readonly status: number
  /** The error code. */
  readonly code: ErrorCode
  /** Extra facts for the technical details. */
  readonly details: Readonly<Record<string, string>>

  constructor(status: number, code: ErrorCode, details: Record<string, string> = {}) {
    super(code)
    this.name = 'ApiError'
    this.status = status
    this.code = code
    this.details = details
  }
}

async function request<T>(path: string, init?: RequestInit): Promise<T> {
  let response: Response
  try {
    response = await fetch(`${API_PREFIX}${path}`, { credentials: 'same-origin', ...init })
  } catch {
    throw new ApiError(0, UNREACHABLE)
  }
  if (!response.ok) {
    throw await toApiError(response)
  }
  if (response.status === NO_CONTENT) {
    return undefined as T
  }
  return (await response.json()) as T
}

function send<T>(method: string, path: string, body?: unknown): Promise<T> {
  if (body === undefined) {
    return request<T>(path, { method })
  }
  return request<T>(path, {
    method,
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify(body),
  })
}

async function toApiError(response: Response): Promise<ApiError> {
  try {
    const body = (await response.json()) as ErrorResponse
    return new ApiError(response.status, body.error.code, body.error.details)
  } catch {
    return new ApiError(response.status, UNREADABLE)
  }
}

/** What a listener of the event stream wants to hear about. */
export interface EventHandlers {
  /** The state of a tool changed, or its download made progress. */
  toolUpdated: (event: ToolUpdated) => void
  /** Something about a channel changed, or one of its checks ended. */
  channelUpdated: (channel: Channel) => void
  /** A first listing or a full check read more videos. */
  taskProgress: (progress: Progress) => void
  /** The pause of YouTube began, got longer or ended. */
  pauseChanged: (pause: Pause | null) => void
  /** A video changed: its status, its file or its date (R-FB-03). */
  videoUpdated: (channelId: string, video: Video) => void
  /** A running download got further (R-QU-04). */
  jobProgress: (download: Download) => void
  apiKeyChanged: (key: ApiKey) => void
  checksProgress: (checkingAll: Counted | null) => void
  /** The queue of downloads changed (R-QU-02). */
  queueUpdated: (queue: Queue) => void
  /** The stream is connected again after a break: events may have been missed. */
  reconnected: () => void
}

/**
 * Open the event stream of this window (docs/ARCHITECTURE.md section 7.6).
 *
 * The browser reconnects by itself after a break. Returns a function that closes the stream.
 */
function openEvents(handlers: EventHandlers): () => void {
  const source = new EventSource(`${API_PREFIX}/events`)
  let broken = false
  const on = <T>(name: string, handle: (data: T) => void): void => {
    source.addEventListener(name, (message) => {
      handle(JSON.parse((message as MessageEvent<string>).data) as T)
    })
  }
  on<ToolUpdated>('tool.updated', handlers.toolUpdated)
  on<components['schemas']['ChannelUpdatedEvent']>('channel.updated', (event) =>
    handlers.channelUpdated(event.channel),
  )
  on<components['schemas']['TaskProgressEvent']>('task.progress', (event) =>
    handlers.taskProgress(event.progress),
  )
  on<components['schemas']['BannerChangedEvent']>('banner.changed', (event) =>
    handlers.pauseChanged(event.youtube_pause),
  )
  on<components['schemas']['VideoUpdatedEvent']>('video.updated', (event) =>
    handlers.videoUpdated(event.channel_id, event.video),
  )
  on<components['schemas']['JobProgressEvent']>('job.progress', (event) =>
    handlers.jobProgress(event.download),
  )
  on<components['schemas']['ApiKeyChangedEvent']>('apikey.changed', (event) =>
    handlers.apiKeyChanged(event.api_key),
  )
  on<components['schemas']['ChecksProgressEvent']>('checks.progress', (event) =>
    handlers.checksProgress(event.checking_all),
  )
  on<components['schemas']['QueueUpdatedEvent']>('queue.updated', (event) =>
    handlers.queueUpdated(event.queue),
  )
  source.addEventListener('error', () => {
    broken = true
  })
  source.addEventListener('open', () => {
    if (broken) {
      broken = false
      handlers.reconnected()
    }
  })
  return () => source.close()
}

export const api = {
  /** Ask the server for its version and the database schema version. */
  getHealth: (): Promise<Health> => request<Health>('/health'),
  /** Ask for the state of every tool, and whether the first-run screen is needed. */
  getTools: (): Promise<ToolsAnswer> => request<ToolsAnswer>('/tools'),
  /** Start installing a tool. The answer is its state right after the start. */
  installTool: (name: ToolName): Promise<Tool> =>
    request<Tool>(`/tools/${name}/install`, { method: 'POST' }),
  /** Ask for the app as it is now: channels, the open channel, the library, the pause. */
  getState: (): Promise<AppState> => request<AppState>('/state'),
  /** Remember which channel is open, for the next start (R-UI-02). */
  setOpenChannel: (channelId: string | null): Promise<AppState> =>
    send<AppState>('PUT', '/state/open-channel', { channel_id: channelId }),
  /** End the pause of YouTube and take up the work that waited (R-ER-05). */
  tryYouTubeNow: (): Promise<AppState> => send<AppState>('POST', '/youtube/try-now'),
  /** Look up the channel the user named, for the preview of the dialog (R-CH-03). */
  lookUpChannel: (text: string): Promise<ChannelLookup> =>
    send<ChannelLookup>('POST', '/channels/lookup', { text }),
  /** Ask for the video count of a preview. It is null when YouTube gave none in time. */
  getPreviewVideoCount: async (channelId: string): Promise<number | null> =>
    (await request<{ video_count: number | null }>(`/channels/lookup/${channelId}/video-count`))
      .video_count,
  /** Show the folder dialog of macOS. The folder is null after Cancel (R-CH-05). */
  chooseFolder: (): Promise<ChosenFolder> => send<ChosenFolder>('POST', '/folders/choose'),
  /** Add a channel that was looked up. Its first listing starts in the background. */
  addChannel: (channel: NewChannel): Promise<AddedChannel> =>
    send<AddedChannel>('POST', '/channels', channel),
  /** Pause or resume a channel (R-CH-31). */
  setChannelPaused: (channelId: string, paused: boolean): Promise<Channel> =>
    send<Channel>('PATCH', `/channels/${channelId}`, { paused }),
  /**
   * Remove a channel with its catalogue, and move its files to the Trash or not (R-CH-32).
   * The answer lists the files macOS refused to move.
   */
  removeChannel: (channelId: string, keepFiles: boolean): Promise<RemovedChannel> =>
    send<RemovedChannel>('DELETE', `/channels/${channelId}?keep_files=${keepFiles}`),
  /** Ask how many files and how much room "Delete the files" moves to the Trash (R-CH-32). */
  getFilesToTrash: (channelId: string): Promise<FilesToTrash> =>
    request<FilesToTrash>(`/channels/${channelId}/files-to-trash`),
  /** Start a quick or a full check of a channel, saying what started it (R-CH-23). */
  checkChannel: (channelId: string, kind: CheckKind, trigger: CheckTrigger): Promise<Channel> =>
    send<Channel>('POST', `/channels/${channelId}/check`, { kind, trigger }),
  /** Cancel the full check of a channel (R-CH-27). */
  cancelCheck: (channelId: string): Promise<{ cancelled: boolean }> =>
    send<{ cancelled: boolean }>('POST', `/channels/${channelId}/check/cancel`),
  /** Start a quick check of every channel that is not paused (R-CH-23). */
  checkAllChannels: (): Promise<{ channels: number }> =>
    send<{ channels: number }>('POST', '/channels/check-all'),
  /** Show the folder of a channel in Finder (R-CH-30). */
  repairDates: (channelId: string): Promise<RepairedDates> =>
    send<RepairedDates>('POST', `/channels/${channelId}/repair-dates`),
  getApiKey: (): Promise<ApiKey> => request<ApiKey>('/settings/api-key'),
  saveApiKey: (key: string): Promise<ApiKey> => send<ApiKey>('PUT', '/settings/api-key', { key }),
  removeApiKey: (): Promise<ApiKey> => send<ApiKey>('DELETE', '/settings/api-key'),
  testApiKey: (key: string | null): Promise<ApiKeyTest> =>
    send<ApiKeyTest>('POST', '/settings/api-key/test', { key }),
  openChannelFolder: async (channelId: string): Promise<void> => {
    await send('POST', `/channels/${channelId}/open-folder`)
  },
  /** Put videos in line to be downloaded, in this order, or at the top (R-MI-01, R-QU-02). */
  mirrorVideos: async (ids: string[], first = false): Promise<QueuedJob[]> =>
    (await send<{ jobs: QueuedJob[] }>('POST', '/videos/mirror', { ids, first })).jobs,
  /** Download synced videos again in their channel's quality (R-QL-06). */
  redownloadVideos: async (ids: string[]): Promise<QueuedJob[]> =>
    (await send<{ jobs: QueuedJob[] }>('POST', '/videos/redownload', { ids })).jobs,
  /** Queue every video of a channel without a file, once (R-MI-04). */
  mirrorMissing: async (channelId: string): Promise<QueuedJob[]> =>
    (await send<{ jobs: QueuedJob[] }>('POST', `/channels/${channelId}/mirror-missing`)).jobs,
  /** Turn auto-mirror of a channel on or off (R-MI-02). */
  setAutoMirror: (channelId: string, on: boolean): Promise<Channel> =>
    send<Channel>('PUT', `/channels/${channelId}/auto-mirror`, { on }),
  /** Answer the question before a large start of auto-mirror (D-095). */
  answerAutoMirror: (channelId: string, answer: AutoMirrorAnswer): Promise<Channel> =>
    send<Channel>('POST', `/channels/${channelId}/auto-mirror/answer`, { answer }),
  /** Leave the missing files of a channel missing, until more are missing (D-092). */
  leaveMissing: (channelId: string): Promise<Channel> =>
    send<Channel>('POST', `/channels/${channelId}/missing/leave`),
  /** Remember list or grid for the whole app (R-UI-03). */
  setView: (view: ViewKind): Promise<AppState> => send<AppState>('PUT', '/state/view', { view }),
  /** Ask for the whole queue (R-QU-02). */
  getQueue: (): Promise<QueueAnswer> => request<QueueAnswer>('/queue'),
  /** Pause all downloads (R-QU-02). */
  pauseQueue: (): Promise<Queue> => send<Queue>('POST', '/queue/pause'),
  /** Resume all downloads (R-QU-02). */
  resumeQueue: (): Promise<Queue> => send<Queue>('POST', '/queue/resume'),
  /** Put the waiting downloads in this order (R-QU-02). */
  reorderQueue: async (jobIds: string[]): Promise<void> => {
    await send('POST', '/queue/reorder', { job_ids: jobIds })
  },
  /** Remove every waiting download (R-QU-02). */
  clearWaiting: (): Promise<{ removed: number }> =>
    send<{ removed: number }>('POST', '/queue/clear-waiting'),
  /** The limit of all downloads together, in MB/s, 0 for none (R-QU-03). */
  setSpeedLimit: (mbps: number): Promise<Queue> =>
    send<Queue>('POST', '/queue/speed-limit', { mbps }),
  /** Go on although the disk space guard paused the queue (R-QU-10). */
  resumeAnyway: (): Promise<Queue> => send<Queue>('POST', '/queue/resume-anyway'),
  /** Look again whether the folder of a channel can be reached (R-QU-11). */
  tryFolderAgain: (channelId: string): Promise<{ available: boolean }> =>
    send<{ available: boolean }>('POST', `/queue/folders/${channelId}/try-again`),
  /** Put a failed video in line again (R-QU-08). */
  retryVideo: (videoId: string): Promise<Video> => send<Video>('POST', `/videos/${videoId}/retry`),
  /** Cancel a download that waits or runs (R-QU-02). */
  cancelJob: (jobId: string): Promise<{ cancelled: boolean }> =>
    send<{ cancelled: boolean }>('POST', `/jobs/${jobId}/cancel`),
  /** Open the file of a video in the default player of macOS (R-UI-10). */
  playVideo: async (videoId: string): Promise<void> => {
    await send('POST', `/videos/${videoId}/play`)
  },
  /** Show the file of a video selected in Finder (R-UI-10). */
  revealVideo: async (videoId: string): Promise<void> => {
    await send('POST', `/videos/${videoId}/reveal`)
  },
  /** Ask for everything the details panel shows of a video (R-UI-08). */
  getVideo: (videoId: string): Promise<VideoDetails> => request<VideoDetails>(`/videos/${videoId}`),
  /** Ask for the catalogue of a channel, newest first (R-CH-10). */
  getChannelVideos: async (channelId: string): Promise<Video[]> =>
    (await request<{ videos: Video[] }>(`/channels/${channelId}/videos`)).videos,
  openEvents,
}

/**
 * The addresses of the cached pictures (R-CH-16). A picture is loaded by the
 * browser itself, from the local server, never from YouTube. A version in the
 * address makes the browser ask again: for an avatar when it was cached anew
 * (R-CH-12), for a thumbnail that was missing when more pictures are cached.
 */
export const pictures = {
  avatar: (channelId: string, version: number): string =>
    `${API_PREFIX}/channels/${channelId}/avatar?v=${version}`,
  previewAvatar: (channelId: string): string => `${API_PREFIX}/channels/lookup/${channelId}/avatar`,
  thumbnail: (videoId: string, version?: number): string =>
    `${API_PREFIX}/videos/${videoId}/thumbnail${version === undefined ? '' : `?v=${version}`}`,
}

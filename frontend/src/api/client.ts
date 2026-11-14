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
export type DatePrecision = components['schemas']['DatePrecision']
export type CheckKind = components['schemas']['CheckKind']
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
  /** Remove a channel with its catalogue. Its folder stays (R-CH-32). */
  removeChannel: async (channelId: string): Promise<void> => {
    await send('DELETE', `/channels/${channelId}`)
  },
  /** Start a quick or a full check of a channel (R-CH-23). */
  checkChannel: (channelId: string, kind: CheckKind): Promise<Channel> =>
    send<Channel>('POST', `/channels/${channelId}/check`, { kind }),
  /** Cancel the full check of a channel (R-CH-27). */
  cancelCheck: (channelId: string): Promise<{ cancelled: boolean }> =>
    send<{ cancelled: boolean }>('POST', `/channels/${channelId}/check/cancel`),
  /** Start a quick check of every channel that is not paused (R-CH-23). */
  checkAllChannels: (): Promise<{ channels: number }> =>
    send<{ channels: number }>('POST', '/channels/check-all'),
  /** Show the folder of a channel in Finder (R-CH-30). */
  openChannelFolder: async (channelId: string): Promise<void> => {
    await send('POST', `/channels/${channelId}/open-folder`)
  },
  /** Ask for the catalogue of a channel, newest first (R-CH-10). */
  getChannelVideos: async (channelId: string): Promise<Video[]> =>
    (await request<{ videos: Video[] }>(`/channels/${channelId}/videos`)).videos,
  openEvents,
}

/**
 * The addresses of the cached pictures (R-CH-16). A picture is loaded by the
 * browser itself, from the local server, never from YouTube. `version` changes
 * when more pictures of a channel are cached, so that a picture that was
 * missing is asked for again.
 */
export const pictures = {
  avatar: (channelId: string, version: number): string =>
    `${API_PREFIX}/channels/${channelId}/avatar?v=${version}`,
  previewAvatar: (channelId: string): string => `${API_PREFIX}/channels/lookup/${channelId}/avatar`,
  thumbnail: (videoId: string, version: number): string =>
    `${API_PREFIX}/videos/${videoId}/thumbnail?v=${version}`,
}

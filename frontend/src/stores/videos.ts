/**
 * The videos store: the catalogue of the channel that is open (R-CH-10), and
 * what happens to its videos while it is open (R-FB-03).
 *
 * It holds one channel at a time. It is loaded when a channel is opened and
 * again whenever a check of that channel ended or the event stream was
 * interrupted, so the list is never stale (docs/ARCHITECTURE.md section 7.6).
 *
 * A change of one video (a status, a file, an exact date) and the progress of
 * a download are kept apart from the list, by video ID. A row reads only its
 * own entries, so a download redraws its own row, never the whole list of a
 * large channel (D-073).
 */
import { defineStore } from 'pinia'
import { reactive, ref } from 'vue'

import {
  api,
  ApiError,
  type Download,
  type ErrorCode,
  type Video,
  type VideoDetails,
  type VideoStatus,
} from '@/api/client'

export type VideosStatus = 'idle' | 'loading' | 'ready' | 'failed'

const UNKNOWN_ERROR: ErrorCode = 'INTERNAL'

/** The statuses of a video whose download waits or runs. */
const ACTIVE: ReadonlySet<VideoStatus> = new Set<VideoStatus>([
  'queued',
  'downloading',
  'processing',
])

export const useVideosStore = defineStore('videos', () => {
  /** The channel whose catalogue is held, or null. */
  const channelId = ref<string | null>(null)
  const videos = ref<Video[]>([])
  const status = ref<VideosStatus>('idle')
  const errorCode = ref<ErrorCode | null>(null)
  /** Videos that changed since the list was loaded, by ID. */
  const changed = reactive(new Map<string, Video>())
  /** The downloads that run, by video ID (R-QU-04). */
  const downloads = reactive(new Map<string, Download>())
  /** The videos whose download the user cancelled, while it still ends (R-QU-02). */
  const cancelling = reactive(new Set<string>())
  /** The video of the details panel, or null when it is closed (R-UI-08). */
  const openVideoId = ref<string | null>(null)
  /** What the details panel shows, once it arrived. */
  const details = ref<VideoDetails | null>(null)

  function forgetChanges(): void {
    changed.clear()
    downloads.clear()
  }

  async function fetchFor(wanted: string): Promise<void> {
    try {
      const loaded = await api.getChannelVideos(wanted)
      // The user may have opened another channel while this answer was on its way.
      if (channelId.value === wanted) {
        videos.value = loaded
        forgetChanges()
        // A download that runs keeps its progress across a new load of the list.
        for (const video of loaded) {
          if (video.download) {
            downloads.set(video.id, video.download)
          }
        }
        status.value = 'ready'
        errorCode.value = null
      }
    } catch (error) {
      if (channelId.value === wanted) {
        errorCode.value = error instanceof ApiError ? error.code : UNKNOWN_ERROR
        status.value = 'failed'
      }
    }
  }

  /** Open the catalogue of a channel. The list is empty until it arrives. */
  async function open(wanted: string): Promise<void> {
    if (channelId.value !== wanted) {
      videos.value = []
      forgetChanges()
      closeDetails()
    }
    channelId.value = wanted
    status.value = 'loading'
    await fetchFor(wanted)
  }

  /** Load the catalogue of the open channel again, keeping what is shown meanwhile. */
  async function reload(): Promise<void> {
    if (channelId.value !== null) {
      await fetchFor(channelId.value)
    }
    if (openVideoId.value !== null) {
      await loadDetails(openVideoId.value)
    }
  }

  /** Forget the catalogue, as when its channel was removed. */
  function close(): void {
    channelId.value = null
    videos.value = []
    status.value = 'idle'
    errorCode.value = null
    forgetChanges()
    closeDetails()
  }

  /** The video as it is now: with the changes the events told. */
  function current(video: Video): Video {
    return changed.get(video.id) ?? video
  }

  /** Take over a video that changed (R-FB-03). Videos of other channels are not held. */
  function applyVideo(ofChannel: string, video: Video): void {
    if (ofChannel !== channelId.value) {
      return
    }
    changed.set(video.id, video)
    if (!ACTIVE.has(video.status)) {
      cancelling.delete(video.id)
    }
    if (video.download === null || video.download === undefined) {
      downloads.delete(video.id)
    } else {
      downloads.set(video.id, video.download)
    }
    if (openVideoId.value === video.id && details.value !== null) {
      void loadDetails(video.id)
    }
  }

  /** Take over how far a download is (R-QU-04). */
  function applyDownload(download: Download): void {
    if (download.channel_id === channelId.value) {
      downloads.set(download.video_id, download)
    }
  }

  /** The running download of a video, or null. */
  function downloadOf(videoId: string): Download | null {
    return downloads.get(videoId) ?? null
  }

  /** Put a video in line to be downloaded (R-MI-01). */
  async function mirror(videoId: string): Promise<void> {
    await api.mirrorVideos([videoId])
  }

  /** Put a failed video in line again (R-QU-08). */
  async function retry(videoId: string): Promise<void> {
    await api.retryVideo(videoId)
  }

  /**
   * Cancel the download of a video that waits or runs (R-QU-02).
   *
   * Until its end arrives the video counts as cancelling: a job that has
   * written files ends only once its temp folder is gone. A job that only
   * asked YouTube ends at once, and its end arrives with the answer.
   */
  async function cancel(jobId: string, videoId: string): Promise<void> {
    cancelling.add(videoId)
    try {
      await api.cancelJob(jobId)
    } catch (error) {
      cancelling.delete(videoId)
      throw error
    }
  }

  /** Whether the user cancelled the download of a video that has not ended yet. */
  function isCancelling(video: Video): boolean {
    return cancelling.has(video.id) && ACTIVE.has(current(video).status)
  }

  /** Open the file of a video in the default player (R-UI-10). */
  async function play(videoId: string): Promise<void> {
    await api.playVideo(videoId)
  }

  /** Show the file of a video in Finder (R-UI-10). */
  async function reveal(videoId: string): Promise<void> {
    await api.revealVideo(videoId)
  }

  async function loadDetails(videoId: string): Promise<void> {
    const loaded = await api.getVideo(videoId)
    if (openVideoId.value === videoId) {
      details.value = loaded
    }
  }

  /** Open the details panel of a video (R-UI-08). */
  async function openDetails(videoId: string): Promise<void> {
    if (openVideoId.value !== videoId) {
      details.value = null
    }
    openVideoId.value = videoId
    await loadDetails(videoId)
  }

  /** Close the details panel. */
  function closeDetails(): void {
    openVideoId.value = null
    details.value = null
  }

  return {
    channelId,
    videos,
    status,
    errorCode,
    openVideoId,
    details,
    open,
    reload,
    close,
    current,
    applyVideo,
    applyDownload,
    downloadOf,
    mirror,
    retry,
    cancel,
    isCancelling,
    play,
    reveal,
    openDetails,
    closeDetails,
  }
})

/**
 * The videos store: the catalogue of the channel that is open (R-CH-10).
 *
 * It holds one channel at a time. It is loaded when a channel is opened and
 * again whenever a check of that channel ended or the event stream was
 * interrupted, so the list is never stale (docs/ARCHITECTURE.md section 7.6).
 */
import { defineStore } from 'pinia'
import { ref } from 'vue'

import { api, ApiError, type ErrorCode, type Video } from '@/api/client'

export type VideosStatus = 'idle' | 'loading' | 'ready' | 'failed'

const UNKNOWN_ERROR: ErrorCode = 'INTERNAL'

export const useVideosStore = defineStore('videos', () => {
  /** The channel whose catalogue is held, or null. */
  const channelId = ref<string | null>(null)
  const videos = ref<Video[]>([])
  const status = ref<VideosStatus>('idle')
  const errorCode = ref<ErrorCode | null>(null)

  async function fetchFor(wanted: string): Promise<void> {
    try {
      const loaded = await api.getChannelVideos(wanted)
      // The user may have opened another channel while this answer was on its way.
      if (channelId.value === wanted) {
        videos.value = loaded
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
  }

  /** Forget the catalogue, as when its channel was removed. */
  function close(): void {
    channelId.value = null
    videos.value = []
    status.value = 'idle'
    errorCode.value = null
  }

  return { channelId, videos, status, errorCode, open, reload, close }
})

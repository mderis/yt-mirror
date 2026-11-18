/**
 * The app store: whether the window is connected to the backend, and the one
 * event stream of the window.
 *
 * Server data lives in stores (docs/CODING-STANDARDS.md section 4). Connecting
 * loads the snapshots (tools, channels) and opens the event stream, whose
 * events this store passes on to the store they belong to. After a break of
 * the stream every snapshot is loaded again, so a missed event can never
 * leave the interface stale (docs/ARCHITECTURE.md section 7.6, R-FB-03).
 */
import { defineStore } from 'pinia'
import { ref } from 'vue'

import { api, ApiError, type ErrorCode, type Health } from '@/api/client'

import { useChannelsStore } from './channels'
import { useQueueStore } from './queue'
import { useToolsStore } from './tools'
import { useUiStore } from './ui'
import { useVideosStore } from './videos'

export type ConnectionStatus = 'connecting' | 'ready' | 'failed'

const UNKNOWN_ERROR: ErrorCode = 'INTERNAL'

export const useAppStore = defineStore('app', () => {
  const status = ref<ConnectionStatus>('connecting')
  const health = ref<Health | null>(null)
  const errorCode = ref<ErrorCode | null>(null)
  let closeStream: (() => void) | null = null

  /** Load every snapshot again. A failure is left to the next event or reconnect. */
  function reload(): void {
    const tools = useToolsStore()
    const channels = useChannelsStore()
    const videos = useVideosStore()
    void tools.load().catch(() => undefined)
    void channels.load().catch(() => undefined)
    void videos.reload()
  }

  /** Open the event stream of the window, once. Does nothing when it is open already. */
  function listen(): void {
    const tools = useToolsStore()
    const channels = useChannelsStore()
    const videos = useVideosStore()
    const queue = useQueueStore()
    const ui = useUiStore()
    closeStream ??= api.openEvents({
      toolUpdated: (event) => tools.apply(event.tool),
      channelUpdated: (channel) => {
        const catalogueChanged = channels.apply(channel)
        if (catalogueChanged && videos.channelId === channel.id) {
          void videos.reload()
        }
      },
      taskProgress: (progress) => channels.applyProgress(progress),
      pauseChanged: (pause) => channels.setPause(pause),
      videoUpdated: (channelId, video) => videos.applyVideo(channelId, video),
      videosChanged: (channelId) => {
        // One summary instead of an event per video: the open list is loaded again.
        if (videos.channelId === channelId) {
          void videos.reload()
        }
      },
      jobProgress: (download) => {
        videos.applyDownload(download)
        queue.applyDownload(download)
      },
      apiKeyChanged: (key) => channels.setApiKey(key),
      checksProgress: (progress) => channels.setCheckingAll(progress),
      queueUpdated: (summary) => queue.apply(summary),
      menuCommand: (command) => ui.receiveCommand(command),
      quitAsked: () => {
        ui.quitAsked = true
      },
      reconnected: reload,
    })
  }

  /** Ask the backend for its health and its snapshots, and remember the answer or the error. */
  async function connect(): Promise<void> {
    status.value = 'connecting'
    errorCode.value = null
    try {
      health.value = await api.getHealth()
      await useToolsStore().load()
      await useChannelsStore().load()
      listen()
      status.value = 'ready'
    } catch (error) {
      health.value = null
      errorCode.value = error instanceof ApiError ? error.code : UNKNOWN_ERROR
      status.value = 'failed'
    }
  }

  return { status, health, errorCode, connect }
})

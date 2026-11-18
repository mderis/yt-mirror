/**
 * The queue store: how the queue of downloads stands, for the queue bar, and
 * the whole queue while the downloads panel is open (R-QU-01 to R-QU-04,
 * design: Downloads.html).
 *
 * The summary comes with the snapshot of the app and with every
 * `queue.updated` event. The panel loads the whole queue when it opens and
 * again after each such event. The progress of every running download, of any
 * channel, is kept from the `job.progress` events, for the speed and the time
 * left of the queue bar.
 */
import { defineStore } from 'pinia'
import { computed, reactive, ref } from 'vue'

import { api, type Download, type Queue, type QueueAnswer } from '@/api/client'

/** The summary of a queue that has nothing in it. */
const EMPTY: Queue = {
  downloading: 0,
  waiting: 0,
  failed: 0,
  paused: false,
  places: 2,
  speed_limit_mbps: 0,
  folders_away: [],
}

/** The speed limits the panel offers, in MB/s; 0 is unlimited (R-QU-03). */
export const SPEED_LIMITS = [0, 5, 2, 1] as const

export const useQueueStore = defineStore('queue', () => {
  const summary = ref<Queue>(EMPTY)
  /** The whole queue, while the panel is open, or null. */
  const full = ref<QueueAnswer | null>(null)
  const panelOpen = ref(false)
  /** How far each running download is, by job (R-QU-04). */
  const progress = reactive(new Map<string, Download>())

  /** Take over how the queue stands, from the snapshot or an event. */
  function setSummary(queue: Queue): void {
    summary.value = queue
    if (queue.downloading === 0) {
      progress.clear()
    }
  }

  /** Take over how the queue stands after a change, and load the panel again when open. */
  function apply(queue: Queue): void {
    setSummary(queue)
    if (panelOpen.value) {
      void load()
    }
  }

  /** Take over how far a download is. */
  function applyDownload(download: Download): void {
    progress.set(download.job_id, download)
  }

  async function load(): Promise<void> {
    const answer = await api.getQueue()
    full.value = answer
    summary.value = answer.queue
    const running = new Set(answer.running.map((item) => item.job_id))
    for (const jobId of [...progress.keys()]) {
      if (!running.has(jobId)) {
        progress.delete(jobId)
      }
    }
  }

  /** Open the downloads panel ("Show queue", View > Show Downloads). */
  async function openPanel(): Promise<void> {
    panelOpen.value = true
    await load()
  }

  function closePanel(): void {
    panelOpen.value = false
    full.value = null
  }

  /** The speed of all running downloads together, in bytes per second, or null. */
  const speed = computed<number | null>(() => {
    let sum = 0
    let known = false
    for (const download of progress.values()) {
      if (download.speed_bps !== null && download.stage !== 'processing') {
        sum += download.speed_bps
        known = true
      }
    }
    return known ? sum : null
  })

  /** About how long the running downloads still take, in seconds, or null. */
  const leftS = computed<number | null>(() => {
    let longest: number | null = null
    for (const download of progress.values()) {
      if (download.left_s !== null) {
        longest = Math.max(longest ?? 0, download.left_s)
      }
    }
    return longest
  })

  async function pause(): Promise<void> {
    summary.value = await api.pauseQueue()
  }

  async function resume(): Promise<void> {
    summary.value = await api.resumeQueue()
  }

  /** Put the waiting downloads in this order (drag and drop, R-QU-02). */
  async function reorder(jobIds: string[]): Promise<void> {
    if (full.value !== null) {
      const byId = new Map(full.value.waiting.map((item) => [item.job_id, item]))
      full.value = {
        ...full.value,
        waiting: jobIds.flatMap((jobId) => {
          const item = byId.get(jobId)
          return item === undefined ? [] : [item]
        }),
      }
    }
    await api.reorderQueue(jobIds)
  }

  /** Move a waiting download up or down by one place, as Alt+Up and Alt+Down do (R-UI-13). */
  async function move(jobId: string, by: -1 | 1): Promise<void> {
    const waiting = full.value?.waiting.map((item) => item.job_id) ?? []
    const from = waiting.indexOf(jobId)
    const to = from + by
    if (from < 0 || to < 0 || to >= waiting.length) {
      return
    }
    const order = [...waiting]
    order.splice(from, 1)
    order.splice(to, 0, jobId)
    await reorder(order)
  }

  async function clearWaiting(): Promise<void> {
    await api.clearWaiting()
  }

  async function setSpeedLimit(mbps: number): Promise<void> {
    summary.value = await api.setSpeedLimit(mbps)
  }

  async function resumeAnyway(): Promise<void> {
    summary.value = await api.resumeAnyway()
  }

  /** Look again whether the folder of a channel is there (R-QU-11). */
  async function tryFolderAgain(channelId: string): Promise<boolean> {
    return (await api.tryFolderAgain(channelId)).available
  }

  return {
    summary,
    full,
    panelOpen,
    progress,
    speed,
    leftS,
    setSummary,
    apply,
    applyDownload,
    load,
    openPanel,
    closePanel,
    pause,
    resume,
    reorder,
    move,
    clearWaiting,
    setSpeedLimit,
    resumeAnyway,
    tryFolderAgain,
  }
})

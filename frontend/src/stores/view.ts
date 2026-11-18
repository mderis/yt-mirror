/**
 * The view store: how the open channel shows its videos, and which are selected.
 *
 * The tab, the search and the order (R-UI-04 to R-UI-06) belong to the window
 * and start anew with each channel. List or grid is one choice of the whole
 * app, kept by the backend (R-UI-03). The selection (R-MI-07) is a set of video
 * IDs with the last one clicked, for Shift-click ranges; it is cleared when the
 * channel, the tab or the search changes, so it never holds videos that are
 * not shown.
 */
import { defineStore } from 'pinia'
import { reactive, ref, shallowRef, watch } from 'vue'

import { api, type ViewKind } from '@/api/client'
import type { Sort, Tab } from '@/features/channel/shown'

export const useViewStore = defineStore('view', () => {
  const view = ref<ViewKind>('list')
  const tab = ref<Tab>('all')
  const search = ref('')
  const sort = ref<Sort>('newest')
  /** The selected videos (R-MI-07). */
  const selected = reactive(new Set<string>())
  /** The video last clicked, where a Shift-click range starts. */
  const anchor = ref<string | null>(null)
  /** The shown videos in their order, for a Shift-click range, read only when clicked. */
  const order = shallowRef<readonly string[]>([])
  /** The video the arrow keys are on, or null (R-UI-13). */
  const cursor = ref<string | null>(null)

  /** Take over the view the backend remembers. */
  function setView(kind: ViewKind): void {
    view.value = kind
  }

  /** Switch between list and grid, and remember it for the whole app (R-UI-03). */
  async function chooseView(kind: ViewKind): Promise<void> {
    view.value = kind
    await api.setView(kind)
  }

  /** Start a channel anew: all videos, no search, newest first, nothing selected. */
  function reset(): void {
    tab.value = 'all'
    search.value = ''
    sort.value = 'newest'
    cursor.value = null
    clearSelection()
  }

  /**
   * Move the current video up or down the shown ones, as the arrow keys do (R-UI-13).
   * Without one, the first or the last shown video becomes current.
   */
  function moveCursor(by: -1 | 1, shown: readonly string[]): void {
    if (shown.length === 0) {
      cursor.value = null
      return
    }
    const at = cursor.value === null ? -1 : shown.indexOf(cursor.value)
    const next = at < 0 ? (by > 0 ? 0 : shown.length - 1) : at + by
    cursor.value = shown[Math.max(0, Math.min(shown.length - 1, next))] ?? null
  }

  /**
   * Take the shown videos in their order. A selected video that is no longer shown,
   * as one that left its tab, is selected no more: the bar acts only on what is seen.
   */
  function showing(ids: readonly string[]): void {
    order.value = ids
    if (selected.size === 0) {
      return
    }
    const seen = new Set(ids)
    for (const id of [...selected]) {
      if (!seen.has(id)) {
        selected.delete(id)
      }
    }
  }

  function clearSelection(): void {
    selected.clear()
    anchor.value = null
  }

  /**
   * Select or unselect a video; with Shift, every shown video from the last one
   * clicked to this one takes its state (R-MI-07).
   *
   * @param shown The shown videos, in their order.
   */
  function pick(videoId: string, on: boolean, shift: boolean, shown: readonly string[]): void {
    const from = anchor.value === null ? -1 : shown.indexOf(anchor.value)
    const to = shown.indexOf(videoId)
    if (shift && from >= 0 && to >= 0) {
      const [low, high] = from < to ? [from, to] : [to, from]
      for (const id of shown.slice(low, high + 1)) {
        if (on) {
          selected.add(id)
        } else {
          selected.delete(id)
        }
      }
    } else if (on) {
      selected.add(videoId)
    } else {
      selected.delete(videoId)
    }
    anchor.value = videoId
  }

  /** Select every shown video, or none when all are selected already (R-MI-07). */
  function toggleAll(shown: readonly string[]): void {
    if (shown.length > 0 && shown.every((id) => selected.has(id))) {
      clearSelection()
      return
    }
    for (const id of shown) {
      selected.add(id)
    }
  }

  watch([tab, search], clearSelection)

  return {
    view,
    tab,
    search,
    sort,
    selected,
    anchor,
    order,
    showing,
    cursor,
    moveCursor,
    setView,
    chooseView,
    reset,
    clearSelection,
    pick,
    toggleAll,
  }
})

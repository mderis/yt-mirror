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
import { reactive, ref, watch } from 'vue'

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
    clearSelection()
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
    setView,
    chooseView,
    reset,
    clearSelection,
    pick,
    toggleAll,
  }
})

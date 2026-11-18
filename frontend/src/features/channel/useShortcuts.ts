/**
 * The keyboard shortcuts of a channel's page (R-UI-13, R-NA-09, docs/DESIGN.md
 * section 7.3, design: Shortcuts.html).
 *
 * Single keys work only while no text field, select or dialog has the focus,
 * so typing is never taken for a command. The arrow keys move the current
 * video; Space selects it; Enter opens its details; P plays it and F shows it
 * in Finder; M mirrors the selected videos, or the current one; Esc closes the
 * details or clears the selection; "/" goes to the search; G switches list and
 * grid; 1 to 9 open the channels of the sidebar; Cmd+A selects every shown
 * video; Cmd+R checks the channel now, under the rule of "Check Now" in the
 * menu bar; "?" opens the list of shortcuts. Exclude (X) arrives with M6.
 */
import { onBeforeUnmount, onMounted, type Ref } from 'vue'
import { useRouter } from 'vue-router'

import type { Video } from '@/api/client'
import { canCheckNow } from '@/features/shell/useMenuBridge'
import { channelRoute } from '@/router'
import { useChannelsStore } from '@/stores/channels'
import { useUiStore } from '@/stores/ui'
import { useVideosStore } from '@/stores/videos'
import { useViewStore } from '@/stores/view'

/** Controls that Space and Enter press: on them, these two keys are theirs, not a shortcut. */
const PRESSABLE =
  'button, a[href], summary, [role="button"], [role="tab"], [role="checkbox"], [role="option"]'

/** Whether a key goes to what has the focus: a field, a select, a menu or a dialog. */
function typing(target: EventTarget | null): boolean {
  if (!(target instanceof HTMLElement)) {
    return false
  }
  const tag = target.tagName
  return (
    tag === 'INPUT' ||
    tag === 'TEXTAREA' ||
    tag === 'SELECT' ||
    target.isContentEditable ||
    target.closest('[role="dialog"], [role="menu"]') !== null
  )
}

/**
 * Listen for the shortcuts while the page is shown.
 *
 * @param channelId The open channel.
 * @param shown The shown videos, as they are now, in their order.
 */
export function useShortcuts(channelId: () => string, shown: Ref<readonly Video[]>): void {
  const router = useRouter()
  const channels = useChannelsStore()
  const videos = useVideosStore()
  const view = useViewStore()
  const ui = useUiStore()

  function current(): Video | undefined {
    return shown.value.find((video) => video.id === view.cursor)
  }

  function onKey(event: KeyboardEvent): void {
    const command = event.metaKey || event.ctrlKey
    if (command && event.key.toLowerCase() === 'r' && !event.shiftKey) {
      // Taken here, the key does not reach the menu bar too: one check, not two.
      event.preventDefault()
      const channel = channels.byId.get(channelId())
      if (channel && canCheckNow(channel)) {
        void ui.run(channels.check(channel.id, 'quick', 'button'))
      }
      return
    }
    if (typing(event.target) || document.querySelector('[role="dialog"]') !== null) {
      return
    }
    const ids = shown.value.map((video) => video.id)
    if (command && event.key.toLowerCase() === 'a') {
      event.preventDefault()
      view.toggleAll(ids)
      return
    }
    if (command || event.altKey) {
      return
    }
    const pressing = event.key === ' ' || event.key === 'Enter'
    if (pressing && event.target instanceof Element && event.target.closest(PRESSABLE) !== null) {
      return
    }
    const video = current()
    const handled = ((): boolean => {
      switch (event.key) {
        case 'ArrowDown':
        case 'ArrowUp':
          view.moveCursor(event.key === 'ArrowDown' ? 1 : -1, ids)
          return true
        case ' ':
          if (video) {
            view.pick(video.id, !view.selected.has(video.id), false, ids)
          }
          return video !== undefined
        case 'Enter':
          if (video) {
            void ui.run(videos.openDetails(video.id))
          }
          return video !== undefined
        case 'Escape':
          if (videos.openVideoId !== null) {
            videos.closeDetails()
          } else {
            view.clearSelection()
          }
          return true
        case 'm':
        case 'M': {
          const chosen = view.selected.size > 0 ? ids.filter((id) => view.selected.has(id)) : []
          const wanted = chosen.length > 0 ? chosen : video ? [video.id] : []
          if (wanted.length > 0) {
            void ui.run(videos.mirrorMany(wanted))
          }
          return wanted.length > 0
        }
        case 'p':
        case 'P':
          if (video?.status === 'synced') {
            void ui.run(videos.play(video.id))
          }
          return video !== undefined
        case 'f':
        case 'F':
          if (video?.status === 'synced') {
            void ui.run(videos.reveal(video.id))
          }
          return video !== undefined
        case '/':
          document.querySelector<HTMLInputElement>('[data-search]')?.focus()
          return true
        case 'g':
        case 'G':
          void ui.run(view.chooseView(view.view === 'list' ? 'grid' : 'list'))
          return true
        case '?':
          ui.shortcutsOpen = true
          return true
        default: {
          const number = Number(event.key)
          const target =
            Number.isInteger(number) && number >= 1 ? channels.channels[number - 1] : undefined
          if (target) {
            void router.push(channelRoute(target.id))
          }
          return target !== undefined
        }
      }
    })()
    if (handled) {
      event.preventDefault()
    }
  }

  onMounted(() => window.addEventListener('keydown', onKey))
  onBeforeUnmount(() => window.removeEventListener('keydown', onKey))
}

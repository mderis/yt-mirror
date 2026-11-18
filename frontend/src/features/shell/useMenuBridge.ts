/**
 * The interface's side of the menu bar (D-094, R-NA-03, R-NA-04, docs/ARCHITECTURE.md
 * section 7.10).
 *
 * The interface tells the app what applies now (an open channel, whether it
 * is paused or checking, whether it has videos to mirror, whether its folder
 * can be reached, the view), and the app enables and titles the menu bar from
 * that. A command chosen in the menu bar arrives as an event and runs exactly
 * what the matching control of the interface runs, under the same conditions.
 */
import { computed, onBeforeUnmount, watch } from 'vue'
import { useRoute } from 'vue-router'

import { api, type Channel, type MenuCommand, type UiState } from '@/api/client'
import { useChannelsStore } from '@/stores/channels'
import { useQueueStore } from '@/stores/queue'
import { useUiStore } from '@/stores/ui'
import { useViewStore } from '@/stores/view'

/** Whether a channel can be checked now: not paused (R-CH-31), and no check of it runs. */
export function canCheckNow(channel: Channel): boolean {
  return !channel.paused && channel.status !== 'checking'
}

/** Whether a channel has videos to mirror: neither synced nor excluded (R-MI-04). */
export function hasMissing(channel: Channel): boolean {
  return channel.videos - channel.synced - channel.excluded > 0
}

/** Report the state for the menu bar while the shell is shown, and run the menu's commands. */
export function useMenuBridge(): void {
  const route = useRoute()
  const channels = useChannelsStore()
  const queue = useQueueStore()
  const view = useViewStore()
  const ui = useUiStore()

  const open = computed(() =>
    route.name === 'channel' ? channels.byId.get(String(route.params.id)) : undefined,
  )

  const state = computed<UiState>(() => {
    const channel = open.value
    return {
      channel_open: channel !== undefined,
      paused: channel?.paused ?? false,
      checking: channel?.status === 'checking',
      has_missing: channel !== undefined && hasMissing(channel),
      folder_available: channel?.status !== 'folder_not_found',
      view: view.view,
      any_unpaused: channels.channels.some((each) => !each.paused),
    }
  })

  // Only a change is sent. A report that fails is sent again with the next change.
  let sent = ''
  watch(
    state,
    (now) => {
      const text = JSON.stringify(now)
      if (text === sent) {
        return
      }
      sent = text
      api.reportUiState(now).catch(() => {
        sent = ''
      })
    },
    { immediate: true },
  )

  function run(command: MenuCommand): void {
    const channel = open.value
    switch (command) {
      case 'add_channel':
        ui.openAddChannel()
        return
      case 'view_list':
      case 'view_grid':
        void ui.run(view.chooseView(command === 'view_list' ? 'list' : 'grid'))
        return
      case 'show_downloads':
        void ui.run(queue.openPanel())
        return
      case 'reload':
        window.location.reload()
        return
      case 'check_all':
        void ui.run(channels.checkAll())
        return
      case 'shortcuts':
        ui.shortcutsOpen = true
        return
      default:
        break
    }
    if (channel === undefined) {
      return
    }
    if (command === 'check_now' && canCheckNow(channel)) {
      void ui.run(channels.check(channel.id, 'quick', 'menu'))
    } else if (command === 'mirror_missing' && hasMissing(channel)) {
      void ui.run(channels.mirrorMissing(channel.id))
    } else if (command === 'toggle_pause') {
      void ui.run(channels.setPaused(channel.id, !channel.paused))
    } else if (command === 'open_folder') {
      void ui.run(channels.openFolder(channel.id))
    }
  }

  onBeforeUnmount(ui.runCommandsWith(run))
}

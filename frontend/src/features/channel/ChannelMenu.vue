<script setup lang="ts">
/**
 * The menu of a channel (R-CH-30, design: Menus.html, docs/DESIGN.md section
 * 8.1). It opens by a right-click on the channel in the sidebar and by the
 * "More actions" button of the channel header. It shows only what can be
 * done: a paused channel is not checked (R-CH-31), so it offers no check.
 */
import { computed } from 'vue'
import { useI18n } from 'vue-i18n'

import type { Channel } from '@/api/client'
import AppMenu, { type MenuItem } from '@/components/AppMenu.vue'
import { useChannelsStore } from '@/stores/channels'
import { useUiStore } from '@/stores/ui'

const props = defineProps<{
  /** The channel the menu is about. */
  channel: Channel
  /** Where the menu opens, in the window. Without it, it opens under its parent. */
  at?: { x: number; y: number } | undefined
}>()

const emit = defineEmits<{
  /** The menu should close. */
  close: []
}>()

const { t } = useI18n()
const channels = useChannelsStore()
const ui = useUiStore()

const items = computed<MenuItem[]>(() => {
  const checks: MenuItem[] = props.channel.paused
    ? []
    : [
        { id: 'check', label: t('channel.menu.check'), icon: 'retry' },
        { id: 'fullCheck', label: t('channel.menu.fullCheck'), icon: 'clock' },
      ]
  const pause: MenuItem = props.channel.paused
    ? { id: 'resume', label: t('channel.menu.resume'), icon: 'resume' }
    : { id: 'pause', label: t('channel.menu.pause'), icon: 'pause' }
  return [
    ...checks,
    pause,
    { id: 'openFolder', label: t('channel.menu.openFolder'), icon: 'folder' },
    {
      id: 'openOnYouTube',
      label: t('channel.menu.openOnYouTube'),
      icon: 'external',
      href: props.channel.url,
    },
    { id: 'remove', label: t('channel.menu.remove'), icon: 'trash', danger: true },
  ]
})

function choose(id: string): void {
  const channelId = props.channel.id
  const actions: Record<string, () => unknown> = {
    check: () => ui.run(channels.check(channelId, 'quick')),
    fullCheck: () => ui.run(channels.check(channelId, 'full')),
    pause: () => ui.run(channels.setPaused(channelId, true)),
    resume: () => ui.run(channels.setPaused(channelId, false)),
    openFolder: () => ui.run(channels.openFolder(channelId)),
    remove: () => ui.askRemove(channelId),
  }
  // "Open on YouTube" is a link: the browser opens it, nothing is left to do here.
  void actions[id]?.()
}
</script>

<template>
  <AppMenu
    :label="t('channel.menu.label', { channel: channel.title })"
    :items="items"
    :at="at"
    @choose="choose"
    @close="emit('close')"
  />
</template>

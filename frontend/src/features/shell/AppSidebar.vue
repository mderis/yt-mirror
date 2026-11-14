<script setup lang="ts">
/**
 * The sidebar (R-UI-01, R-CH-34, design: Main.html): the channels with their
 * avatar, name, one status line and count of new videos, "Check all channels
 * now", "Add channel", and the free space of the disk the library is on.
 *
 * Activity, Settings, Help and "Report a problem" arrive with milestone M7
 * (docs/DESIGN.md section 8.6).
 */
import { computed, ref } from 'vue'
import { useI18n } from 'vue-i18n'
import { useRoute, useRouter } from 'vue-router'

import { pictures } from '@/api/client'
import AppIcon from '@/components/AppIcon.vue'
import IconButton from '@/components/IconButton.vue'
import SidebarItem from '@/components/SidebarItem.vue'
import { BrandIcon } from '@/design/brand'
import { useStatusLine } from '@/features/channel/status'
import { formatBytes, formatNumber } from '@/format'
import { channelRoute } from '@/router'
import { useChannelsStore } from '@/stores/channels'
import { useUiStore } from '@/stores/ui'

const { t } = useI18n()
const route = useRoute()
const router = useRouter()
const channels = useChannelsStore()
const ui = useUiStore()
const statusOf = useStatusLine()

const checkingAll = ref(false)

const entries = computed(() =>
  channels.channels.map((channel) => ({
    channel,
    status: statusOf(channel),
    badge:
      channel.new_videos > 0
        ? t('channelStatus.newBadge', { count: formatNumber(channel.new_videos) })
        : undefined,
  })),
)

const freeSpace = computed(() =>
  channels.disk
    ? t('shell.freeSpace', {
        size: formatBytes(channels.disk.free_bytes),
        disk: channels.disk.name,
      })
    : '',
)

async function checkAll(): Promise<void> {
  checkingAll.value = true
  await ui.run(channels.checkAll())
  checkingAll.value = false
}
</script>

<template>
  <nav
    class="flex w-64 flex-none flex-col gap-4 border-r border-line bg-surface-side px-3 py-5"
    :aria-label="t('shell.channels')"
  >
    <div class="flex items-center gap-2 px-2">
      <BrandIcon class="size-6" />
      <span class="font-heading text-heading-sm font-semibold">{{ t('app.name') }}</span>
    </div>

    <div class="flex min-h-0 flex-1 flex-col gap-1">
      <div class="flex items-center justify-between pl-2">
        <h2 class="text-label text-text-muted uppercase">{{ t('shell.channels') }}</h2>
        <IconButton
          icon="retry"
          size="sm"
          :label="t('shell.checkAll')"
          :busy="checkingAll"
          @press="checkAll"
        />
      </div>
      <ul class="flex min-h-0 flex-col gap-1 overflow-y-auto">
        <li v-for="entry in entries" :key="entry.channel.id">
          <SidebarItem
            :title="entry.channel.title"
            :status="entry.status.text"
            :status-icon="entry.status.icon"
            :status-tone="entry.status.tone"
            :avatar="pictures.avatar(entry.channel.id, entry.channel.avatar_version)"
            :new-videos="entry.badge"
            :selected="route.params.id === entry.channel.id"
            @open="router.push(channelRoute(entry.channel.id))"
            @menu="ui.openMenu({ channelId: entry.channel.id, at: $event })"
          />
        </li>
      </ul>
      <button
        type="button"
        class="mt-1 flex min-h-11 flex-none items-center justify-center gap-2 rounded-md border border-dashed border-line-strong font-medium duration-fast hover:bg-surface-raised focus-visible:outline-2 focus-visible:outline-offset-2 focus-visible:outline-accent"
        data-add-channel
        @click="ui.openAddChannel()"
      >
        <AppIcon name="plus" size="md" />
        {{ t('shell.addChannel') }}
      </button>
    </div>

    <p class="px-2 text-label text-text-muted" data-free-space>{{ freeSpace }}</p>
  </nav>
</template>

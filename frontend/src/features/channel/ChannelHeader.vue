<script setup lang="ts">
/**
 * The header of the channel page (R-CH-35, R-CH-30, design: Main.html,
 * StateLoading.html, docs/DESIGN.md sections 8.1 and 8.3): the name, the
 * totals, the result and the times of the last check and the last full check,
 * and the actions. While the first listing runs it shows the progress of the
 * listing instead (R-CH-11).
 */
import { computed, ref } from 'vue'
import { useI18n } from 'vue-i18n'

import type { Channel } from '@/api/client'
import AppButton from '@/components/AppButton.vue'
import AppIcon from '@/components/AppIcon.vue'
import IconButton from '@/components/IconButton.vue'
import type { IconName } from '@/components/icons'
import ProgressBar from '@/components/ProgressBar.vue'
import { formatBytes, formatNumber } from '@/format'
import { useAgo } from '@/format/useAgo'
import { useChannelsStore } from '@/stores/channels'
import { useUiStore } from '@/stores/ui'

import ChannelMenu from './ChannelMenu.vue'
import { isBeingListed } from './status'

const props = defineProps<{
  /** The channel that is open. */
  channel: Channel
}>()

const { t } = useI18n()
const agoText = useAgo()
const channels = useChannelsStore()
const ui = useUiStore()

const menuOpen = ref(false)
const listing = computed(() => isBeingListed(props.channel))

const listingText = computed(() => {
  const found = props.channel.progress?.done ?? 0
  return found > 0
    ? t('channel.listing.found', { count: formatNumber(found) }, found)
    : t('channel.listing.starting')
})

const totals = computed(() => [
  t('channel.videos', { count: formatNumber(props.channel.videos) }, props.channel.videos),
  t('channel.synced', { count: formatNumber(props.channel.synced) }),
  t('channel.excluded', { count: formatNumber(props.channel.excluded) }),
  formatBytes(props.channel.size_bytes),
])

/** The result of the last check: its words, its icon and its colour. */
const check = computed<{ text: string; icon: IconName; look: string } | null>(() => {
  const channel = props.channel
  if (channel.status === 'could_not_check') {
    return { text: t('channel.lastCheckFailed'), icon: 'warning', look: 'text-err-text' }
  }
  if (channel.status === 'checking') {
    return { text: t('channel.checking'), icon: 'retry', look: 'text-text-dim' }
  }
  if (channel.paused) {
    return { text: t('channel.paused'), icon: 'pause', look: 'text-text-muted' }
  }
  if (channel.last_check_at === null) {
    return null
  }
  const ago = agoText(channel.last_check_at)
  const fresh = channel.new_videos
  return fresh > 0
    ? {
        text: t('channel.checkedWithNew', { ago, count: formatNumber(fresh) }, fresh),
        icon: 'video',
        look: 'text-warn-text',
      }
    : { text: t('channel.checked', { ago }), icon: 'check', look: 'text-ok-text' }
})

const fullCheck = computed(() =>
  props.channel.last_full_check_at === null
    ? null
    : t('channel.fullCheck', { ago: agoText(props.channel.last_full_check_at) }),
)
</script>

<template>
  <header class="flex flex-wrap items-center gap-3 px-7 pt-5 pb-3">
    <div class="min-w-0 flex-1 basis-80">
      <h1 class="truncate font-heading text-heading-lg leading-heading font-semibold">
        {{ channel.title }}
      </h1>
      <template v-if="listing">
        <p class="mt-2 flex items-center gap-2" role="status" data-listing>
          <AppIcon name="retry" size="md" />
          {{ listingText }}
        </p>
        <ProgressBar class="mt-3 max-w-105" :value="null" :label="t('channel.listing.progress')" />
        <p class="mt-2 text-meta text-text-muted">{{ t('channel.listing.hint') }}</p>
      </template>
      <template v-else>
        <p class="mt-1 flex flex-wrap items-center gap-2 text-text-muted" data-totals>
          <template v-for="(total, index) in totals" :key="index">
            <span v-if="index > 0" aria-hidden="true">{{ t('app.separator') }}</span>
            <span>{{ total }}</span>
          </template>
        </p>
        <p class="mt-1 flex flex-wrap items-center gap-2" data-check>
          <span v-if="check" class="inline-flex items-center gap-1" :class="check.look">
            <AppIcon :name="check.icon" size="md" />
            {{ check.text }}
          </span>
          <span v-if="check && fullCheck" class="text-text-muted" aria-hidden="true">{{
            t('app.separator')
          }}</span>
          <span v-if="fullCheck" class="text-text-muted">{{ fullCheck }}</span>
        </p>
      </template>
    </div>
    <AppButton
      v-if="!listing && !channel.paused"
      icon="retry"
      :busy="channel.status === 'checking'"
      @press="ui.run(channels.check(channel.id, 'quick'))"
    >
      {{ t('channel.checkNow') }}
    </AppButton>
    <AppButton v-if="!listing" icon="folder" @press="ui.run(channels.openFolder(channel.id))">
      {{ t('channel.openFolder') }}
    </AppButton>
    <!-- A press on the button must not count as a click beside the menu, which closes it. -->
    <div class="relative" @mousedown.stop>
      <IconButton icon="more" :label="t('channel.moreActions')" @press="menuOpen = !menuOpen" />
      <ChannelMenu v-if="menuOpen" :channel="channel" @close="menuOpen = false" />
    </div>
  </header>
</template>

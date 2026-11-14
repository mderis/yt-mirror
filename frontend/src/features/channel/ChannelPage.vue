<script setup lang="ts">
/**
 * The page of a channel (design: Main.html, StateLoading.html,
 * StateError.html): the header, what is going on with its checks, and the
 * list of its videos. It shows what the stores know and loads the catalogue
 * of the channel that is open.
 */
import { computed, watch } from 'vue'
import { useI18n } from 'vue-i18n'

import AppBanner from '@/components/AppBanner.vue'
import AppButton from '@/components/AppButton.vue'
import EmptyState from '@/components/EmptyState.vue'
import IconButton from '@/components/IconButton.vue'
import SkeletonBlock from '@/components/SkeletonBlock.vue'
import { useErrorTexts } from '@/i18n/errors'
import { useChannelsStore } from '@/stores/channels'
import { useUiStore } from '@/stores/ui'
import { useVideosStore } from '@/stores/videos'

import ChannelHeader from './ChannelHeader.vue'
import CheckFailedBanner from './CheckFailedBanner.vue'
import FullCheckProgress from './FullCheckProgress.vue'
import { isBeingListed } from './status'
import VideoList from './VideoList.vue'

const props = defineProps<{
  /** The channel ID, from the address. */
  id: string
}>()

const { t } = useI18n()
const textsOf = useErrorTexts()
const channels = useChannelsStore()
const videos = useVideosStore()
const ui = useUiStore()

const channel = computed(() => channels.byId.get(props.id))
const fullCheck = computed(() =>
  channel.value?.progress?.kind === 'full_check' ? channel.value.progress : null,
)
const existing = computed(() => ui.existingChannelId === props.id)
const loadError = computed(() =>
  videos.status === 'failed' && videos.errorCode ? textsOf(videos.errorCode) : null,
)

/** The skeleton rows of a first listing, as wide as the mockup draws them. */
const SKELETON_ROWS = [
  ['w-1/2', 'w-1/4'],
  ['w-2/5', 'w-1/5'],
  ['w-1/2', 'w-1/4'],
  ['w-2/5', 'w-1/5'],
] as const

// The catalogue belongs to the open channel. A channel that is not known is left to the shell.
watch(
  () => (channel.value ? props.id : null),
  (id) => {
    if (id !== null) {
      void videos.open(id)
      void ui.run(channels.rememberOpen(id))
    }
  },
  { immediate: true },
)
</script>

<template>
  <main v-if="channel" class="flex h-full min-w-0 flex-col">
    <ChannelHeader :channel="channel" />
    <div
      v-if="existing || channel.last_check_error || fullCheck"
      class="flex flex-col gap-3 px-7 pb-3"
    >
      <AppBanner v-if="existing" tone="info" data-banner="existing">
        {{ t('addChannel.existing', { channel: channel.title }) }}
        <template #action>
          <IconButton
            icon="close"
            size="sm"
            :label="t('error.dismiss')"
            @press="ui.noteExisting(null)"
          />
        </template>
      </AppBanner>
      <CheckFailedBanner
        v-if="channel.last_check_error"
        :channel="channel"
        :code="channel.last_check_error"
      />
      <FullCheckProgress v-if="fullCheck" :progress="fullCheck" />
    </div>
    <!-- It can be focused, so that the list can be scrolled with the keyboard (R-UI-13). -->
    <div
      class="min-h-0 flex-1 overflow-y-auto border-t border-line focus-visible:outline-2 focus-visible:-outline-offset-2 focus-visible:outline-accent"
      role="region"
      tabindex="0"
      :aria-label="t('channel.list.region')"
    >
      <div v-if="isBeingListed(channel)" data-skeleton-list>
        <div
          v-for="(widths, index) in SKELETON_ROWS"
          :key="index"
          class="flex items-center gap-3 border-b border-line px-4 py-2"
        >
          <SkeletonBlock class="h-18 w-32 flex-none" />
          <div class="flex flex-1 flex-col gap-2">
            <SkeletonBlock class="h-3" :class="widths[0]" />
            <SkeletonBlock class="h-3" :class="widths[1]" />
          </div>
        </div>
      </div>
      <div v-else-if="loadError" class="p-7">
        <AppBanner tone="error" data-banner="list-failed">
          <p class="font-medium">{{ t('channel.list.failed') }}</p>
          <p class="text-meta">{{ loadError.happened }} {{ loadError.action }}</p>
          <template #action>
            <AppButton icon="retry" @press="videos.open(channel.id)">
              {{ t('channel.list.retry') }}
            </AppButton>
          </template>
        </AppBanner>
      </div>
      <EmptyState
        v-else-if="
          channel.first_listed_at !== null &&
          videos.status === 'ready' &&
          videos.videos.length === 0
        "
        icon="video"
        :title="t('channel.empty.title')"
      >
        {{ t('channel.empty.text') }}
      </EmptyState>
      <VideoList v-else :videos="videos.videos" :channel-id="channel.id" />
    </div>
  </main>
</template>

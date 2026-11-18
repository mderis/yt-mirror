<script setup lang="ts">
/**
 * The page of a channel (design: Main.html, StateLoading.html,
 * StateError.html): the header, what is going on with its checks, and the
 * list of its videos. It shows what the stores know and loads the catalogue
 * of the channel that is open.
 */
import { computed, ref, watch } from 'vue'
import { useI18n } from 'vue-i18n'

import AppBanner from '@/components/AppBanner.vue'
import AppButton from '@/components/AppButton.vue'
import EmptyState from '@/components/EmptyState.vue'
import IconButton from '@/components/IconButton.vue'
import SkeletonBlock from '@/components/SkeletonBlock.vue'
import { formatNumber } from '@/format'
import { useErrorTexts } from '@/i18n/errors'
import { useChannelsStore } from '@/stores/channels'
import { useUiStore } from '@/stores/ui'
import { useVideosStore } from '@/stores/videos'
import { useViewStore } from '@/stores/view'

import QueueBar from '@/features/queue/QueueBar.vue'

import BulkBar from './BulkBar.vue'
import ChannelHeader from './ChannelHeader.vue'
import ChannelToolbar from './ChannelToolbar.vue'
import ExactDatesNotice from './ExactDatesNotice.vue'
import CheckFailedBanner from './CheckFailedBanner.vue'
import FullCheckProgress from './FullCheckProgress.vue'
import { shownVideos } from './shown'
import { isBeingListed } from './status'
import VideoDetails from './VideoDetails.vue'
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
const view = useViewStore()

const channel = computed(() => channels.byId.get(props.id))
/** The element that scrolls the list, for its virtual drawing (R-UI-07). */
const scroller = ref<HTMLElement | null>(null)
/** Every video of the channel as it is now, with what the events told. */
const current = computed(() => videos.videos.map((video) => videos.current(video)))
/** The videos of the tab that match the search, in the chosen order (R-UI-04 to R-UI-06). */
const shown = computed(() => shownVideos(current.value, view.tab, view.search, view.sort))
const shownIds = computed(() => shown.value.map((video) => video.id))
/** The selected videos, in the order they are shown (R-MI-07). */
const selected = computed(() => shown.value.filter((video) => view.selected.has(video.id)))
const ready = computed(
  () =>
    channel.value !== undefined &&
    !isBeingListed(channel.value) &&
    videos.status === 'ready' &&
    videos.videos.length > 0,
)
/** What "Repair dates" did for this channel, as a sentence (R-DT-09). */
const repaired = computed(() => {
  const result = ui.repaired
  if (result === null || result.channel !== channel.value?.title) {
    return null
  }
  const values = {
    channel: result.channel,
    checked: formatNumber(result.checked),
    repaired: formatNumber(result.repaired),
    failed: formatNumber(result.failed),
  }
  if (result.failed > 0) {
    return t('repaired.failed', values)
  }
  return result.repaired > 0 ? t('repaired.some', values) : t('repaired.none', values)
})
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
      view.reset()
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
      v-if="
        existing ||
        channel.status === 'folder_not_found' ||
        channel.last_check_error ||
        fullCheck ||
        channel.key_notice ||
        channel.exact_dates?.offer_key ||
        channel.missing_held ||
        repaired
      "
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
      <AppBanner
        v-if="channel.status === 'folder_not_found'"
        tone="error"
        data-banner="folder-not-found"
      >
        <p class="font-medium">{{ t('channel.folderNotFound.title') }}</p>
        <p class="text-meta">
          {{ t('channel.folderNotFound.text', { folder: channel.folder }) }}
        </p>
        <template #action>
          <AppButton icon="trash" @press="ui.askRemove(channel.id)">
            {{ t('channel.folderNotFound.remove') }}
          </AppButton>
        </template>
      </AppBanner>
      <CheckFailedBanner
        v-if="channel.last_check_error"
        :channel="channel"
        :code="channel.last_check_error"
      />
      <AppBanner v-if="channel.missing_held" data-banner="missing-held">
        <p class="font-medium">
          {{ t('channel.missing.title', { count: formatNumber(channel.missing_held) }) }}
        </p>
        <p class="text-meta">{{ t('channel.missing.text') }}</p>
        <template #action>
          <AppButton icon="download" @press="ui.run(channels.mirrorMissing(channel.id))">
            {{ t('channel.missing.mirror') }}
          </AppButton>
          <AppButton variant="ghost" @press="ui.run(channels.leaveMissing(channel.id))">
            {{ t('channel.missing.leave') }}
          </AppButton>
        </template>
      </AppBanner>
      <FullCheckProgress v-if="fullCheck" :progress="fullCheck" />
      <ExactDatesNotice :channel="channel" />
      <AppBanner v-if="repaired" tone="info" data-banner="repaired">
        {{ repaired }}
        <template #action>
          <IconButton
            icon="close"
            size="sm"
            :label="t('error.dismiss')"
            @press="ui.closeRepaired()"
          />
        </template>
      </AppBanner>
    </div>
    <!-- It can be focused, so that the list can be scrolled with the keyboard (R-UI-13).
         It is `relative`, so that nothing inside it is placed against the window (R-UI-01). -->
    <ChannelToolbar v-if="ready" :videos="current" :shown="shownIds" />
    <div class="flex min-h-0 flex-1 border-t border-line">
      <div
        ref="scroller"
        class="relative min-h-0 min-w-0 flex-1 overflow-y-auto focus-visible:outline-2 focus-visible:-outline-offset-2 focus-visible:outline-accent"
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
        <EmptyState
          v-else-if="ready && shown.length === 0"
          icon="video"
          :title="view.search.trim() ? t('channel.list.noMatch') : t('channel.list.emptyTab')"
        >
          {{
            view.search.trim()
              ? t('channel.list.noMatchText', { search: view.search.trim() })
              : t('channel.list.emptyTabText')
          }}
        </EmptyState>
        <VideoList
          v-else
          :videos="shown"
          :channel-id="channel.id"
          :view="view.view"
          :scroller="scroller"
        />
      </div>
      <VideoDetails v-if="videos.openVideoId !== null" />
    </div>
    <BulkBar v-if="selected.length > 0" :videos="selected" />
    <QueueBar />
  </main>
</template>

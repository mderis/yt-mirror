<script setup lang="ts">
/**
 * The downloads panel (R-QU-01 to R-QU-04, R-QU-08, design: Downloads.html).
 *
 * At the top: the speed limit of all downloads together (R-QU-03), "Pause all"
 * or "Resume all" (R-QU-02) and how the queue stands. Then the downloads that
 * run, each with its progress and Cancel; the ones that wait, in their order,
 * which drag and drop changes, and Alt with the arrow keys for the keyboard
 * (R-QU-02, R-UI-13); "Clear waiting", which asks first (R-UI-12); a paced one
 * says until when it waits (D-090). Then the failed videos with their reason
 * and Retry (R-QU-08). At the foot: that unfinished downloads continue at the
 * next start (R-QU-05). Details of an error and "Retry all" arrive with M7.
 */
import { computed, ref } from 'vue'
import { useI18n } from 'vue-i18n'

import type { QueueItem } from '@/api/client'
import AppButton from '@/components/AppButton.vue'
import AppDialog from '@/components/AppDialog.vue'
import AppIcon from '@/components/AppIcon.vue'
import IconButton from '@/components/IconButton.vue'
import ProgressBar from '@/components/ProgressBar.vue'
import SelectField from '@/components/SelectField.vue'
import { formatBytes, formatDuration, formatNumber, formatTime, roughTime } from '@/format'
import { clock } from '@/format/clock'
import { useChannelsStore } from '@/stores/channels'
import { SPEED_LIMITS, useQueueStore } from '@/stores/queue'
import { useUiStore } from '@/stores/ui'
import { useVideosStore } from '@/stores/videos'

const { t, te } = useI18n()
const queue = useQueueStore()
const channels = useChannelsStore()
const videos = useVideosStore()
const ui = useUiStore()

const full = computed(() => queue.full)
const summary = computed(() => queue.summary)
const asking = ref(false)
/** The waiting download being dragged, by its job. */
const dragged = ref<string | null>(null)

const speedOptions = computed(() =>
  SPEED_LIMITS.map((mbps) => ({ value: String(mbps), label: t(`queue.speeds.${mbps}`) })),
)

const line = computed(() => {
  const parts: string[] = []
  parts.push(t('queue.downloading', { count: formatNumber(summary.value.downloading) }))
  parts.push(t('queue.waiting', { count: formatNumber(summary.value.waiting) }))
  if (queue.leftS !== null && summary.value.downloading > 0) {
    const left = roughTime(queue.leftS)
    parts.push(
      t('queue.left', { time: t(`rough.${left.unit}`, { count: left.count }, left.count) }),
    )
  }
  if (queue.speed !== null && summary.value.downloading > 0) {
    parts.push(t('queue.speed', { size: formatBytes(Math.round(queue.speed)) }))
  }
  if (channels.disk) {
    parts.push(t('queue.free', { size: formatBytes(channels.disk.free_bytes) }))
  }
  return parts.join(` ${t('app.separator')} `)
})

/** The line under a running download: channel, stage and percent, quality, speed, time left. */
function runningFacts(item: QueueItem): string {
  const download = queue.progress.get(item.job_id) ?? item.download ?? null
  const parts = [item.channel_title]
  if (download?.stage === 'processing') {
    parts.push(t('queue.processing'))
  } else if (download) {
    if (download.fraction !== null) {
      parts.push(
        `${t(`channel.list.stage.${download.stage}`)} ${Math.round(download.fraction * 100)}%`,
      )
    }
    if (download.height !== null) {
      parts.push(t('channel.list.quality', { height: download.height }))
    }
    if (download.speed_bps !== null) {
      parts.push(t('channel.list.speed', { size: formatBytes(Math.round(download.speed_bps)) }))
    }
    if (download.left_s !== null) {
      const left = roughTime(download.left_s)
      parts.push(
        t('channel.list.left', {
          time: t(`rough.${left.unit}`, { count: left.count }, left.count),
        }),
      )
    }
  }
  return parts.join(` ${t('app.separator')} `)
}

function progressOf(item: QueueItem): number | null {
  const download = queue.progress.get(item.job_id) ?? item.download ?? null
  return download?.stage === 'processing' ? null : (download?.fraction ?? null)
}

/** The line under a waiting download: channel, length, quality, and until when it is paced. */
function waitingFacts(item: QueueItem): string {
  const parts = [item.channel_title]
  if (item.duration_s !== null) {
    parts.push(formatDuration(item.duration_s))
  }
  parts.push(
    item.quality === 'best'
      ? t('addChannel.qualities.best')
      : t('channel.list.quality', { height: item.quality }),
  )
  if (item.paced_until) {
    parts.push(t('channel.list.paced', { time: formatTime(item.paced_until, clock.timeZone) }))
  }
  return parts.join(` ${t('app.separator')} `)
}

function reasonOf(code: string | null): string {
  const key = `channel.list.reason.${(code ?? 'internal').toLowerCase()}`
  return te(key) ? t(key) : t('channel.list.reason.internal')
}

function drop(target: string): void {
  const moving = dragged.value
  dragged.value = null
  const waiting = full.value?.waiting.map((item) => item.job_id) ?? []
  if (moving === null || moving === target || !waiting.includes(moving)) {
    return
  }
  const order = waiting.filter((jobId) => jobId !== moving)
  order.splice(order.indexOf(target), 0, moving)
  void ui.run(queue.reorder(order))
}

function onKey(event: KeyboardEvent, jobId: string): void {
  if (!event.altKey || (event.key !== 'ArrowUp' && event.key !== 'ArrowDown')) {
    return
  }
  event.preventDefault()
  void ui.run(queue.move(jobId, event.key === 'ArrowUp' ? -1 : 1))
}

async function clearWaiting(): Promise<void> {
  asking.value = false
  await queue.clearWaiting()
}
</script>

<template>
  <aside
    class="flex w-115 max-w-full flex-col gap-4 overflow-y-auto border-l border-line bg-surface-side p-5 shadow-overlay"
    :aria-label="t('queue.title')"
    data-downloads-panel
  >
    <div class="flex items-center gap-2">
      <h2 class="flex-1 font-heading text-heading-sm font-semibold">{{ t('queue.title') }}</h2>
      <IconButton icon="close" :label="t('queue.close')" @press="queue.closePanel()" />
    </div>
    <div class="flex flex-wrap items-end gap-3">
      <SelectField
        class="w-48"
        :model-value="String(summary.speed_limit_mbps)"
        :label="t('queue.speedLimit')"
        :options="speedOptions"
        label-hidden
        @update:model-value="(value: string) => ui.run(queue.setSpeedLimit(Number(value)))"
      />
      <AppButton
        :icon="summary.paused ? 'resume' : 'pause'"
        @press="ui.run(summary.paused ? queue.resume() : queue.pause())"
      >
        {{ summary.paused ? t('queue.resumeAll') : t('queue.pauseAll') }}
      </AppButton>
    </div>
    <p class="text-meta text-text-muted" role="status" data-queue-line>{{ line }}</p>

    <template v-if="full">
      <section v-if="full.running.length > 0" class="flex flex-col gap-2" data-running>
        <h3 class="font-medium">
          {{ t('queue.now', { count: formatNumber(summary.places) }) }}
        </h3>
        <div
          v-for="item in full.running"
          :key="item.job_id"
          class="flex flex-col gap-1 rounded-md bg-surface p-3"
          :data-job="item.job_id"
        >
          <div class="flex items-center gap-2">
            <span class="min-w-0 flex-1 truncate font-medium">{{ item.title }}</span>
            <AppButton
              variant="ghost"
              :aria-label="t('channel.list.cancelOf', { title: item.title })"
              @press="ui.run(videos.cancel(item.job_id, item.video_id))"
            >
              {{ t('queue.cancel') }}
            </AppButton>
          </div>
          <span class="text-meta text-warn-text">{{ runningFacts(item) }}</span>
          <ProgressBar
            :value="progressOf(item)"
            :label="t('channel.list.progressLabel', { title: item.title })"
          />
        </div>
      </section>

      <section v-if="full.waiting.length > 0" class="flex flex-col gap-2" data-waiting>
        <div class="flex items-center gap-2">
          <h3 class="flex-1 font-medium">
            {{ t('queue.waitingTitle', { count: formatNumber(full.waiting.length) }) }}
          </h3>
          <AppButton variant="ghost" @press="asking = true">
            {{ t('queue.clearWaiting') }}
          </AppButton>
        </div>
        <p class="text-meta text-text-muted">{{ t('queue.moveHint') }}</p>
        <ol class="flex flex-col gap-1">
          <li
            v-for="item in full.waiting"
            :key="item.job_id"
            class="flex items-center gap-2 rounded-md bg-surface p-2 focus:outline-2 focus:outline-offset-2 focus:outline-accent"
            :class="{ 'opacity-50': dragged === item.job_id }"
            draggable="true"
            tabindex="0"
            :data-job="item.job_id"
            @dragstart="dragged = item.job_id"
            @dragend="dragged = null"
            @dragover.prevent
            @drop.prevent="drop(item.job_id)"
            @keydown="onKey($event, item.job_id)"
          >
            <AppIcon name="grip" class="flex-none cursor-grab text-text-muted" />
            <div class="flex min-w-0 flex-1 flex-col">
              <span class="truncate">{{ item.title }}</span>
              <span class="text-meta text-text-muted">{{ waitingFacts(item) }}</span>
            </div>
            <IconButton
              icon="close"
              size="sm"
              :label="t('queue.remove', { title: item.title })"
              @press="ui.run(videos.cancel(item.job_id, item.video_id))"
            />
          </li>
        </ol>
      </section>

      <section v-if="full.failed.length > 0" class="flex flex-col gap-2" data-failed>
        <h3 class="font-medium">
          {{ t('queue.failedTitle', { count: formatNumber(full.failed.length) }) }}
        </h3>
        <div
          v-for="item in full.failed"
          :key="item.video_id"
          class="flex items-center gap-2 rounded-md bg-surface p-2"
          :data-failed-video="item.video_id"
        >
          <AppIcon name="warning" class="flex-none text-err-text" />
          <div class="flex min-w-0 flex-1 flex-col">
            <span class="truncate">{{ item.title }}</span>
            <span class="text-meta text-err-text">
              {{ reasonOf(item.error_code) }}
              <template v-if="item.attempts > 0">
                {{ t('queue.tried', { count: formatNumber(item.attempts + 1) }) }}
              </template>
            </span>
          </div>
          <AppButton v-if="!item.gone" @press="ui.run(videos.retry(item.video_id))">
            {{ t('queue.retry') }}
          </AppButton>
        </div>
      </section>

      <p
        v-if="full.running.length + full.waiting.length + full.failed.length === 0"
        class="text-text-muted"
      >
        {{ t('queue.empty') }}
      </p>
    </template>

    <p class="mt-auto text-meta text-text-muted">{{ t('queue.footer') }}</p>

    <AppDialog
      v-if="asking"
      :title="t('queue.clearTitle')"
      :close-label="t('queue.clearCancel')"
      @close="asking = false"
    >
      <p>{{ t('queue.clearText', { count: formatNumber(full?.waiting.length ?? 0) }) }}</p>
      <template #actions>
        <AppButton variant="ghost" @press="asking = false">{{ t('queue.clearCancel') }}</AppButton>
        <AppButton variant="danger" @press="ui.run(clearWaiting())">
          {{ t('queue.clearConfirm') }}
        </AppButton>
      </template>
    </AppDialog>
  </aside>
</template>

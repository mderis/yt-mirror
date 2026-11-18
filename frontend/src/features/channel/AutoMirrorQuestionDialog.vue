<script setup lang="ts">
/**
 * The question before a large start of auto-mirror (R-MI-02, D-095): auto-mirror
 * never starts many downloads silently. It is asked for one channel at a time,
 * in the order of the sidebar: when auto-mirror is turned on for a channel with
 * more than a few videos to download, and at the first start of the version
 * that brings auto-mirror for every channel stored with it on. Until the answer
 * the channel mirrors nothing by itself.
 *
 * The three answers: mirror them all, only new videos from now on (the date
 * limit becomes today), or turn auto-mirror off. Closing the dialog answers
 * nothing: it comes back the next time the app looks at the channel.
 */
import { computed, ref } from 'vue'
import { useI18n } from 'vue-i18n'

import type { AutoMirrorAnswer, Channel } from '@/api/client'
import AppButton from '@/components/AppButton.vue'
import AppDialog from '@/components/AppDialog.vue'
import { formatBytes, formatNumber } from '@/format'
import { useChannelsStore } from '@/stores/channels'
import { useUiStore } from '@/stores/ui'

const props = defineProps<{
  /** The channel that waits for the answer. */
  channel: Channel
}>()

const emit = defineEmits<{
  /** Closed without an answer. */
  close: []
}>()

const { t } = useI18n()
const channels = useChannelsStore()
const ui = useUiStore()
const answering = ref<AutoMirrorAnswer | null>(null)

const question = computed(() => props.channel.auto_mirror_question ?? null)
const values = computed(() => ({
  channel: props.channel.title,
  count: formatNumber(question.value?.count ?? 0),
  size: formatBytes(question.value?.estimated_bytes ?? 0),
}))

async function answer(choice: AutoMirrorAnswer): Promise<void> {
  answering.value = choice
  try {
    await channels.answerAutoMirror(props.channel.id, choice)
  } finally {
    answering.value = null
  }
}
</script>

<template>
  <AppDialog
    :title="t('channel.autoMirror.question.title', values)"
    :close-label="t('channel.autoMirror.question.close')"
    data-dialog="auto-mirror"
    @close="emit('close')"
  >
    <p>{{ t('channel.autoMirror.question.text', values) }}</p>
    <template #actions>
      <AppButton
        variant="ghost"
        :busy="answering === 'turn_off'"
        @press="ui.run(answer('turn_off'))"
      >
        {{ t('channel.autoMirror.question.turnOff') }}
      </AppButton>
      <AppButton :busy="answering === 'only_new'" @press="ui.run(answer('only_new'))">
        {{ t('channel.autoMirror.question.onlyNew') }}
      </AppButton>
      <AppButton
        variant="primary"
        icon="download"
        :busy="answering === 'mirror_all'"
        @press="ui.run(answer('mirror_all'))"
      >
        {{ t('channel.autoMirror.question.mirrorAll', values) }}
      </AppButton>
    </template>
  </AppDialog>
</template>

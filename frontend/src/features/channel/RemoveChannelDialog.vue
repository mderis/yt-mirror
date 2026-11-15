<script setup lang="ts">
/**
 * The remove channel dialog (R-CH-32, design: RemoveChannel.html). Removing
 * cannot be undone, so it is confirmed here. "Keep the files" is the default.
 * "Delete the files" moves every file the app tracks for the channel to the
 * Trash, never away for good: the dialog says how many and how much room,
 * and that the other files of the folder stay.
 */
import { computed, onMounted, ref } from 'vue'
import { useI18n } from 'vue-i18n'

import { ApiError, type Channel, type ErrorCode, type FilesToTrash } from '@/api/client'
import AppButton from '@/components/AppButton.vue'
import AppDialog from '@/components/AppDialog.vue'
import RadioGroup from '@/components/RadioGroup.vue'
import { formatBytes, formatNumber } from '@/format'
import { useErrorTexts } from '@/i18n/errors'
import { useChannelsStore } from '@/stores/channels'
import { useVideosStore } from '@/stores/videos'

const props = defineProps<{
  /** The channel that is to be removed. */
  channel: Channel
}>()

const emit = defineEmits<{
  /** The dialog should close: the channel was removed, or the user left. */
  close: []
}>()

const { t } = useI18n()
const textsOf = useErrorTexts()
const channels = useChannelsStore()
const videos = useVideosStore()

const UNKNOWN_ERROR: ErrorCode = 'INTERNAL'
const KEEP = 'keep'
const DELETE = 'delete'
const choice = ref(KEEP)
const toTrash = ref<FilesToTrash | null>(null)
const removing = ref(false)
const failure = ref<ErrorCode | null>(null)
const failureTexts = computed(() => (failure.value ? textsOf(failure.value) : null))

const downloaded = computed(() =>
  props.channel.synced > 0
    ? t(
        'removeChannel.downloaded',
        {
          count: formatNumber(props.channel.synced),
          size: formatBytes(props.channel.size_bytes),
        },
        props.channel.synced,
      )
    : null,
)

const options = computed(() => [
  {
    value: KEEP,
    label: t('removeChannel.keep'),
    hint: t('removeChannel.keepHint', { folder: props.channel.folder }),
  },
  {
    value: DELETE,
    label: t('removeChannel.delete'),
    hint:
      toTrash.value === null
        ? undefined
        : t(
            'removeChannel.deleteHint',
            {
              count: formatNumber(toTrash.value.files),
              size: formatBytes(toTrash.value.size_bytes),
            },
            toTrash.value.files,
          ),
  },
])

onMounted(async () => {
  try {
    toTrash.value = await channels.filesToTrash(props.channel.id)
  } catch {
    toTrash.value = null
  }
})

async function remove(): Promise<void> {
  removing.value = true
  failure.value = null
  try {
    await channels.remove(props.channel.id, choice.value === KEEP)
    if (videos.channelId === props.channel.id) {
      videos.close()
    }
    emit('close')
  } catch (error) {
    failure.value = error instanceof ApiError ? error.code : UNKNOWN_ERROR
  } finally {
    removing.value = false
  }
}
</script>

<template>
  <AppDialog
    :title="t('removeChannel.title', { channel: channel.title })"
    :close-label="t('removeChannel.close')"
    @close="emit('close')"
  >
    <p>{{ t('removeChannel.body') }}</p>
    <p v-if="downloaded" class="font-medium text-text" data-downloaded>{{ downloaded }}</p>
    <RadioGroup
      v-model="choice"
      class="break-all"
      :legend="t('removeChannel.files')"
      :options="options"
      data-folder
    />
    <p v-if="failureTexts" class="text-err-text" role="alert">
      {{ failureTexts.happened }} {{ failureTexts.action }}
    </p>
    <template #actions>
      <AppButton variant="ghost" @press="emit('close')">{{ t('removeChannel.cancel') }}</AppButton>
      <AppButton variant="danger" icon="trash" :busy="removing" @press="remove">
        {{ t('removeChannel.remove') }}
      </AppButton>
    </template>
  </AppDialog>
</template>

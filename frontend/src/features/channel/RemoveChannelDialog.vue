<script setup lang="ts">
/**
 * The remove channel dialog (R-CH-32, design: RemoveChannel.html). Removing
 * cannot be undone, so it is confirmed here. The folder of the channel always
 * stays in milestone M2: the choice to move downloaded files to the Trash
 * arrives with the downloads of milestone M3.
 */
import { computed, ref } from 'vue'
import { useI18n } from 'vue-i18n'

import { ApiError, type Channel, type ErrorCode } from '@/api/client'
import AppButton from '@/components/AppButton.vue'
import AppDialog from '@/components/AppDialog.vue'
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
const removing = ref(false)
const failure = ref<ErrorCode | null>(null)
const failureTexts = computed(() => (failure.value ? textsOf(failure.value) : null))

async function remove(): Promise<void> {
  removing.value = true
  failure.value = null
  try {
    await channels.remove(props.channel.id)
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
    <p class="break-all text-text-muted" data-folder>
      {{ t('removeChannel.folder', { folder: channel.folder }) }}
    </p>
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

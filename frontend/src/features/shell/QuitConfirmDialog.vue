<script setup lang="ts">
/**
 * The question before a quit while downloads run (R-QU-12, R-NA-06, design:
 * QuitConfirm.html). The app holds the quit and asks here; "Quit" tells the
 * app to go on, "Keep running" closes the question and changes nothing.
 * "Do not ask again" of the design is not in the spec, so it is left out.
 */
import { computed } from 'vue'
import { useI18n } from 'vue-i18n'

import { api } from '@/api/client'
import AppButton from '@/components/AppButton.vue'
import AppDialog from '@/components/AppDialog.vue'
import { formatNumber } from '@/format'
import { useQueueStore } from '@/stores/queue'
import { useUiStore } from '@/stores/ui'

const emit = defineEmits<{
  /** The question closed. */
  close: []
}>()

const { t } = useI18n()
const queue = useQueueStore()
const ui = useUiStore()

const running = computed(() =>
  t(
    'quit.running',
    {
      downloading: formatNumber(queue.summary.downloading),
      waiting: formatNumber(queue.summary.waiting),
    },
    queue.summary.downloading,
  ),
)

async function quit(): Promise<void> {
  emit('close')
  await api.confirmQuit()
}
</script>

<template>
  <AppDialog
    :title="t('quit.title')"
    :close-label="t('quit.keep')"
    data-dialog="quit"
    @close="emit('close')"
  >
    <div class="flex flex-col gap-3">
      <p>{{ running }}</p>
      <div class="flex flex-col gap-1">
        <p class="font-medium">{{ t('quit.ifQuit') }}</p>
        <ul class="flex list-disc flex-col gap-1 pl-5 text-text-muted">
          <li>{{ t('quit.stop') }} {{ t('quit.resume') }}</li>
          <li>{{ t('quit.noChecks') }}</li>
        </ul>
      </div>
    </div>
    <template #actions>
      <AppButton variant="ghost" @press="emit('close')">{{ t('quit.keep') }}</AppButton>
      <AppButton variant="primary" @press="ui.run(quit())">{{ t('quit.confirm') }}</AppButton>
    </template>
  </AppDialog>
</template>

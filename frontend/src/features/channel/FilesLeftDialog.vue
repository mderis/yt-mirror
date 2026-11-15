<script setup lang="ts">
/**
 * Says which files a removal could not move to the Trash (R-CH-32). The
 * channel is gone already: macOS refused these files, for example because
 * they are locked, and they are still in the folder.
 */
import { computed } from 'vue'
import { useI18n } from 'vue-i18n'

import AppButton from '@/components/AppButton.vue'
import AppDialog from '@/components/AppDialog.vue'
import { formatNumber } from '@/format'
import type { FilesLeft } from '@/stores/ui'

const props = defineProps<{
  /** The channel, its folder and the files left in it. */
  left: FilesLeft
}>()

const emit = defineEmits<{
  /** The user read the message. */
  close: []
}>()

const { t } = useI18n()

/** At most this many names are listed; the rest are counted. */
const SHOWN = 10
const shown = computed(() => props.left.files.slice(0, SHOWN))
const more = computed(() => props.left.files.length - shown.value.length)
</script>

<template>
  <AppDialog
    :title="t('filesLeft.title', { channel: left.channel })"
    :close-label="t('filesLeft.close')"
    @close="emit('close')"
  >
    <p role="alert">
      {{
        t(
          'filesLeft.body',
          { count: formatNumber(left.files.length), folder: left.folder },
          left.files.length,
        )
      }}
    </p>
    <ul class="break-all font-mono text-meta" data-files-left>
      <li v-for="file in shown" :key="file">{{ file }}</li>
    </ul>
    <p v-if="more > 0">{{ t('filesLeft.more', { count: formatNumber(more) }, more) }}</p>
    <template #actions>
      <AppButton @press="emit('close')">{{ t('filesLeft.done') }}</AppButton>
    </template>
  </AppDialog>
</template>

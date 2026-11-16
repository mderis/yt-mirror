<script setup lang="ts">
/**
 * Says which files a removal of a channel with "Delete the files" left in its
 * folder, each with its reason (R-CH-32): macOS refused it, another video is
 * inside, its video could not be checked, or it leads outside the folder. The
 * channel is gone already; these files are still there.
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
    <ul class="flex flex-col gap-1 break-all text-meta" data-files-left>
      <li v-for="kept in shown" :key="kept.file">
        <span class="font-mono">{{ kept.file }}</span>
        {{ ' ' }}
        <span class="text-text-dim">{{ t(`filesLeft.reasons.${kept.reason}`) }}</span>
      </li>
    </ul>
    <p v-if="more > 0">{{ t('filesLeft.more', { count: formatNumber(more) }, more) }}</p>
    <template #actions>
      <AppButton @press="emit('close')">{{ t('filesLeft.done') }}</AppButton>
    </template>
  </AppDialog>
</template>

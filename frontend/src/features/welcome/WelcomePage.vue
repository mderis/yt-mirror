<script setup lang="ts">
/**
 * The welcome screen of an app without channels (R-UI-02, design:
 * Welcome.html). What the user pastes here goes into the add channel dialog,
 * which looks the channel up. "Change in Settings" arrives with the settings
 * of milestone M7.
 */
import { ref } from 'vue'
import { useI18n } from 'vue-i18n'

import AppButton from '@/components/AppButton.vue'
import AppIcon from '@/components/AppIcon.vue'
import TextField from '@/components/TextField.vue'
import { useChannelsStore } from '@/stores/channels'
import { useUiStore } from '@/stores/ui'

const { t } = useI18n()
const channels = useChannelsStore()
const ui = useUiStore()

const POINTS = ['pick', 'exclude', 'names'] as const
const text = ref('')

function add(): void {
  ui.openAddChannel(text.value.trim())
  text.value = ''
}
</script>

<template>
  <main class="flex h-full flex-col items-center justify-center gap-4 px-6 py-12 text-center">
    <h1 class="font-heading text-heading-lg leading-heading font-semibold">
      {{ t('welcome.title') }}
    </h1>
    <p class="max-w-130 text-text-muted">{{ t('welcome.intro') }}</p>
    <div class="flex w-full max-w-150 flex-wrap items-start justify-center gap-2">
      <TextField
        v-model="text"
        class="min-w-80 flex-1 text-left"
        :label="t('welcome.field')"
        hide-label
        :placeholder="t('welcome.placeholder')"
        @enter="add"
      />
      <AppButton variant="primary" icon="plus" @press="add">{{ t('welcome.add') }}</AppButton>
    </div>
    <ul class="mt-3 flex flex-wrap justify-center gap-6 text-text-dim">
      <li v-for="point in POINTS" :key="point" class="flex items-center gap-2">
        <AppIcon name="check" size="md" />
        {{ t(`welcome.points.${point}`) }}
      </li>
    </ul>
    <p class="text-meta text-text-muted" data-library>
      {{ t('welcome.savedIn', { folder: channels.libraryFolder }) }}
    </p>
  </main>
</template>

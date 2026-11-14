<script setup lang="ts">
/**
 * The placeholder page: shows that the window, the interface and the backend
 * work together. The first-run screen comes before it (M1). The shell of
 * milestone M2 replaces it. A missing or broken tool shows its banner here
 * (R-IN-04).
 */
import { computed } from 'vue'
import { useI18n } from 'vue-i18n'

import { BrandIcon } from '@/design/brand'
import ToolBanners from '@/features/tools/ToolBanners.vue'
import { useAppStore } from '@/stores/app'

const { t, te } = useI18n()
const app = useAppStore()

/** The text key of the current error, when the texts of its code exist already. */
const errorText = computed(() => {
  const key = `errors.${(app.errorCode ?? '').toLowerCase()}`
  return te(`${key}.happened`) ? key : null
})
</script>

<template>
  <main class="flex h-full flex-col items-center justify-center gap-6 bg-bg p-8 text-center">
    <BrandIcon class="size-20" />
    <h1 class="font-heading text-heading-lg leading-heading font-semibold text-text">
      {{ t('app.name') }}
    </h1>

    <div v-if="app.status === 'ready' && app.health" class="flex flex-col items-center gap-1">
      <ToolBanners class="mb-5 max-w-170 text-left" />
      <p class="text-body-lg text-text-dim">{{ t('placeholder.running') }}</p>
      <p class="text-meta text-text-muted">
        {{ t('placeholder.version', { version: app.health.version }) }}
      </p>
    </div>

    <p v-else-if="app.status === 'connecting'" class="text-body-lg text-text-muted" role="status">
      {{ t('placeholder.connecting') }}
    </p>

    <div v-else class="flex flex-col items-center gap-4" role="alert">
      <div class="flex flex-col gap-1 rounded-lg bg-err-bg px-6 py-4 text-err-text">
        <template v-if="errorText">
          <p class="text-body-lg font-medium">{{ t(`${errorText}.happened`) }}</p>
          <p class="text-body">{{ t(`${errorText}.doing`) }}</p>
          <p class="text-body">{{ t(`${errorText}.action`) }}</p>
        </template>
        <p v-else class="text-body-lg font-medium">{{ t('placeholder.failed') }}</p>
        <p v-if="app.errorCode" class="font-mono text-meta">
          {{ t('placeholder.errorCode', { code: app.errorCode }) }}
        </p>
      </div>
      <button
        type="button"
        class="h-11 rounded-md bg-accent px-5 text-body font-medium text-on-accent duration-fast hover:opacity-90 focus-visible:outline-2 focus-visible:outline-offset-2 focus-visible:outline-accent"
        @click="app.connect()"
      >
        {{ t('placeholder.retry') }}
      </button>
    </div>
  </main>
</template>

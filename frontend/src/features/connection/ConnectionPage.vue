<script setup lang="ts">
/**
 * The page before the window is connected to its backend. It says that the
 * window is connecting, or what went wrong, with a real button that tries
 * again (R-ER-04).
 */
import { computed } from 'vue'
import { useI18n } from 'vue-i18n'

import AppButton from '@/components/AppButton.vue'
import { BrandIcon } from '@/design/brand'
import { useErrorTexts } from '@/i18n/errors'
import { useAppStore } from '@/stores/app'

const { t } = useI18n()
const app = useAppStore()
const textsOf = useErrorTexts()

const error = computed(() => (app.errorCode ? textsOf(app.errorCode) : null))
</script>

<template>
  <main class="flex h-full flex-col items-center justify-center gap-6 bg-bg p-8 text-center">
    <BrandIcon class="size-20" />
    <h1 class="font-heading text-heading-lg leading-heading font-semibold text-text">
      {{ t('app.name') }}
    </h1>

    <div v-if="error" class="flex flex-col items-center gap-4" role="alert">
      <div class="flex flex-col gap-1 rounded-lg bg-err-bg px-6 py-4 text-err-text">
        <p class="text-body-lg font-medium">{{ error.happened }}</p>
        <p v-if="error.doing" class="text-body">{{ error.doing }}</p>
        <p v-if="error.action" class="text-body">{{ error.action }}</p>
        <p class="font-mono text-meta">{{ t('error.code', { code: app.errorCode }) }}</p>
      </div>
      <AppButton variant="primary" icon="retry" @press="app.connect()">
        {{ t('connection.retry') }}
      </AppButton>
    </div>

    <p v-else class="text-body-lg text-text-muted" role="status">
      {{ t('connection.connecting') }}
    </p>
  </main>
</template>

/**
 * The app store: whether the window is connected to the backend, and its versions.
 *
 * Server data lives in stores (docs/CODING-STANDARDS.md section 4). This one
 * grows into the `/api/state` snapshot in milestone M2.
 */
import { defineStore } from 'pinia'
import { ref } from 'vue'

import { api, ApiError, type Health } from '@/api/client'

export type ConnectionStatus = 'connecting' | 'ready' | 'failed'

const UNKNOWN_ERROR = 'INTERNAL'

export const useAppStore = defineStore('app', () => {
  const status = ref<ConnectionStatus>('connecting')
  const health = ref<Health | null>(null)
  const errorCode = ref<string | null>(null)

  /**
   * Ask the backend for its health and remember the answer or the error code.
   * The error code stays null when the backend could not be reached at all.
   */
  async function connect(): Promise<void> {
    status.value = 'connecting'
    errorCode.value = null
    try {
      health.value = await api.getHealth()
      status.value = 'ready'
    } catch (error) {
      health.value = null
      errorCode.value = error instanceof ApiError ? error.code : UNKNOWN_ERROR
      status.value = 'failed'
    }
  }

  return { status, health, errorCode, connect }
})

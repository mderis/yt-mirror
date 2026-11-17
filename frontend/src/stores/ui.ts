/**
 * The interface store: what is open on top of the pages, and the error of the
 * last action that failed.
 *
 * It holds no server data. Dialogs and the channel menu are opened from
 * several places (the sidebar, the welcome screen, the channel page), so
 * their state lives here and the shell draws them once.
 */
import { defineStore } from 'pinia'
import { ref } from 'vue'

import { ApiError, type ErrorCode, type KeptFile } from '@/api/client'

const UNKNOWN_ERROR: ErrorCode = 'INTERNAL'

/** Files a removal could not move to the Trash, shown once the channel is gone (R-CH-32). */
export interface FilesLeft {
  channel: string
  folder: string
  /** Every file that stayed, with why. */
  files: KeptFile[]
}

/** Where a menu opens: at a place of the window, or under the button that opened it. */
/** What "Repair dates" did, for the channel page (R-DT-09). */
export interface Repaired {
  channel: string
  checked: number
  repaired: number
  failed: number
}

export interface MenuPlace {
  channelId: string
  at?: { x: number; y: number }
}

export const useUiStore = defineStore('ui', () => {
  /** The text the add channel dialog starts with. Null while it is closed. */
  const addChannelText = ref<string | null>(null)
  /** The channel the remove dialog asks about, or null. */
  const removeChannelId = ref<string | null>(null)
  /** The channel whose menu is open, and where. */
  const menu = ref<MenuPlace | null>(null)
  /** The channel that was added before and was opened instead of added again (R-CH-04). */
  const existingChannelId = ref<string | null>(null)
  /** The code of the last action that failed, until the user dismisses it (R-ER-02). */
  const actionError = ref<ErrorCode | null>(null)
  /** The files a removal left in the folder, until the user closes the message. */
  const filesLeft = ref<FilesLeft | null>(null)
  /** Whether the guide of the optional API key is open (R-DT-12). */
  const apiKeyOpen = ref(false)
  /** What the last "Repair dates" did, until the user dismisses it. */
  const repaired = ref<Repaired | null>(null)

  /** Open the add channel dialog, with what the user already typed. */
  function openAddChannel(text = ''): void {
    existingChannelId.value = null
    addChannelText.value = text
  }

  function closeAddChannel(): void {
    addChannelText.value = null
  }

  /** Ask whether a channel should be removed. */
  function askRemove(channelId: string): void {
    removeChannelId.value = channelId
  }

  function closeRemove(): void {
    removeChannelId.value = null
  }

  /** Say which files a removal could not move to the Trash (R-CH-32). */
  function showFilesLeft(left: FilesLeft): void {
    filesLeft.value = left
  }

  function closeFilesLeft(): void {
    filesLeft.value = null
  }

  /** Open the menu of a channel. */
  /** Open the guide of the optional API key. Only ever by a click: never by itself (R-DT-12). */
  function openApiKey(): void {
    apiKeyOpen.value = true
  }

  function closeApiKey(): void {
    apiKeyOpen.value = false
  }

  function showRepaired(result: Repaired): void {
    repaired.value = result
  }

  function closeRepaired(): void {
    repaired.value = null
  }

  function openMenu(place: MenuPlace): void {
    menu.value = place
  }

  function closeMenu(): void {
    menu.value = null
  }

  /** Say that a channel was opened because it existed already (R-CH-04). */
  function noteExisting(channelId: string | null): void {
    existingChannelId.value = channelId
  }

  function dismissError(): void {
    actionError.value = null
  }

  /**
   * Run an action of the user. When it fails, its error code is kept for the
   * banner of the shell instead of being lost.
   *
   * @returns Whether the action worked.
   */
  async function run(action: Promise<unknown>): Promise<boolean> {
    try {
      await action
      actionError.value = null
      return true
    } catch (error) {
      actionError.value = error instanceof ApiError ? error.code : UNKNOWN_ERROR
      return false
    }
  }

  return {
    addChannelText,
    removeChannelId,
    menu,
    existingChannelId,
    actionError,
    filesLeft,
    apiKeyOpen,
    repaired,
    showRepaired,
    closeRepaired,
    openApiKey,
    closeApiKey,
    openAddChannel,
    closeAddChannel,
    askRemove,
    closeRemove,
    showFilesLeft,
    closeFilesLeft,
    openMenu,
    closeMenu,
    noteExisting,
    dismissError,
    run,
  }
})

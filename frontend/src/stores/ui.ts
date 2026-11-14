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

import { ApiError, type ErrorCode } from '@/api/client'

const UNKNOWN_ERROR: ErrorCode = 'INTERNAL'

/** Where a menu opens: at a place of the window, or under the button that opened it. */
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

  /** Open the menu of a channel. */
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
    openAddChannel,
    closeAddChannel,
    askRemove,
    closeRemove,
    openMenu,
    closeMenu,
    noteExisting,
    dismissError,
    run,
  }
})

/**
 * The tools store: the state of every tool the app needs (R-IN-03, R-IN-04).
 *
 * It is filled from `/api/tools` and kept current by the `tool.updated`
 * events of the event stream. After a break of the stream it loads the
 * snapshot again, so a missed event cannot leave the interface stale.
 */
import { defineStore } from 'pinia'
import { computed, ref } from 'vue'

import { api, ApiError, type ErrorCode, type Tool, type ToolName } from '@/api/client'

const UNKNOWN_ERROR: ErrorCode = 'INTERNAL'

/** A tool that is neither in order nor on its way. */
function needsAttention(tool: Tool): boolean {
  return tool.status === 'missing' || tool.status === 'broken' || tool.status === 'failed'
}

export const useToolsStore = defineStore('tools', () => {
  const tools = ref<Tool[]>([])
  /** True from the moment the backend asks for the first-run screen until the user leaves it. */
  const inSetup = ref(false)
  let closeStream: (() => void) | null = null

  const allReady = computed(
    () => tools.value.length > 0 && tools.value.every((tool) => tool.status === 'ok'),
  )
  const installing = computed(() => tools.value.some((tool) => tool.status === 'installing'))
  /** The tools that are not usable and not being installed, in display order. */
  const troubled = computed(() => tools.value.filter(needsAttention))

  function apply(tool: Tool): void {
    const index = tools.value.findIndex((known) => known.name === tool.name)
    if (index === -1) {
      tools.value.push(tool)
    } else {
      tools.value[index] = tool
    }
  }

  /** Load the state of every tool. Throws an ApiError when the backend refuses. */
  async function load(): Promise<void> {
    const answer = await api.getTools()
    tools.value = answer.tools
    if (answer.setup_required) {
      inSetup.value = true
    }
  }

  /** Keep the tools current from the event stream. Does nothing when it listens already. */
  function listen(): void {
    closeStream ??= api.openEvents({
      toolUpdated: (event) => apply(event.tool),
      reconnected: () => void load().catch(() => undefined),
    })
  }

  /** Stop listening to the event stream. */
  function stopListening(): void {
    closeStream?.()
    closeStream = null
  }

  /** Start installing a tool. A refusal of the backend shows as a failed tool with its code. */
  async function install(name: ToolName): Promise<void> {
    try {
      apply(await api.installTool(name))
    } catch (error) {
      const known = tools.value.find((tool) => tool.name === name)
      if (known) {
        apply({
          ...known,
          status: 'failed',
          progress: null,
          error_code: error instanceof ApiError ? error.code : UNKNOWN_ERROR,
        })
      }
    }
  }

  /**
   * Start the next tool of the first-run screen: the first one that is
   * missing or broken and that the app can install, one at a time (R-IN-03).
   * A tool whose installation failed waits for "Try again".
   */
  async function installNextMissing(): Promise<void> {
    if (installing.value) {
      return
    }
    const next = tools.value.find(
      (tool) => tool.installable && (tool.status === 'missing' || tool.status === 'broken'),
    )
    if (next) {
      await install(next.name)
    }
  }

  /** Leave the first-run screen. */
  function finishSetup(): void {
    inSetup.value = false
  }

  return {
    tools,
    inSetup,
    allReady,
    installing,
    troubled,
    load,
    listen,
    stopListening,
    install,
    installNextMissing,
    finishSetup,
  }
})

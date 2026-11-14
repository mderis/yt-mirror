/**
 * The tools store: the state of every tool the app needs (R-IN-03, R-IN-04).
 *
 * It is filled from `/api/tools` and kept current by the `tool.updated`
 * events of the event stream, which the app store passes on (`apply`). After
 * a break of the stream the app store loads the snapshot again, so a missed
 * event cannot leave the interface stale.
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

  const allReady = computed(
    () => tools.value.length > 0 && tools.value.every((tool) => tool.status === 'ok'),
  )
  const installing = computed(() => tools.value.some((tool) => tool.status === 'installing'))
  /** The tools that are not usable and not being installed, in display order. */
  const troubled = computed(() => tools.value.filter(needsAttention))

  /** Take over the new state of one tool, as an event of the stream tells it. */
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

  /**
   * Start installing a tool. A refusal of the backend shows as a failed tool with its code.
   *
   * The answer of the request and the events of the stream race each other. A
   * small tool can be installed before the answer arrives, and the answer
   * ("installing") must then not replace the newer state from the stream.
   */
  async function install(name: ToolName): Promise<void> {
    const before = tools.value.find((tool) => tool.name === name)
    const untouched = (): boolean => tools.value.find((tool) => tool.name === name) === before
    try {
      const started = await api.installTool(name)
      if (untouched()) {
        apply(started)
      }
    } catch (error) {
      if (before && untouched()) {
        apply({
          ...before,
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
    apply,
    install,
    installNextMissing,
    finishSetup,
  }
})

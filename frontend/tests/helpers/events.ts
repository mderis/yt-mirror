/** A stand-in for the browser's EventSource, so tests can play the event stream. */
import { vi } from 'vitest'

import type { Tool } from '@/api/client'

type Listener = (message: { data: string }) => void

export class FakeEventSource {
  /** Every stream that was opened, newest last. */
  static opened: FakeEventSource[] = []

  readonly url: string
  closed = false
  private readonly listeners = new Map<string, Listener[]>()

  constructor(url: string) {
    this.url = url
    FakeEventSource.opened.push(this)
  }

  addEventListener(name: string, listener: Listener): void {
    this.listeners.set(name, [...(this.listeners.get(name) ?? []), listener])
  }

  close(): void {
    this.closed = true
  }

  /** Play an event of the server. */
  emit(name: string, data: unknown = {}): void {
    for (const listener of this.listeners.get(name) ?? []) {
      listener({ data: JSON.stringify(data) })
    }
  }

  /** Play the event that tells about a tool. */
  toolUpdated(tool: Tool, setupRequired = true): void {
    this.emit('tool.updated', { tool, setup_required: setupRequired })
  }
}

/** Use the stand-in for this test and return a way to reach the newest stream. */
export function fakeEventStream(): () => FakeEventSource {
  FakeEventSource.opened = []
  vi.stubGlobal('EventSource', FakeEventSource)
  return () => {
    const newest = FakeEventSource.opened.at(-1)
    if (!newest) {
      throw new Error('No event stream was opened')
    }
    return newest
  }
}

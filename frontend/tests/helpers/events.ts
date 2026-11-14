/** A stand-in for the browser's EventSource, so tests can play the event stream. */
import { vi } from 'vitest'

import type { Channel, Pause, Progress, Tool } from '@/api/client'

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

  /** Play the event that tells about a channel. */
  channelUpdated(channel: Channel): void {
    this.emit('channel.updated', { channel })
  }

  /** Play the event that tells how far a first listing or a full check has come. */
  taskProgress(progress: Progress): void {
    this.emit('task.progress', { progress })
  }

  /** Play the event that tells about the pause of YouTube, or its end. */
  pauseChanged(pause: Pause | null): void {
    this.emit('banner.changed', { youtube_pause: pause })
  }

  /** Play a break of the stream and its return. */
  breakAndReturn(): void {
    this.emit('error')
    this.emit('open')
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

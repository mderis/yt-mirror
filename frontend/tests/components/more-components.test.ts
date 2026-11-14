import { fireEvent, render, screen, within } from '@testing-library/vue'
import { describe, expect, it } from 'vitest'
import { h, nextTick } from 'vue'

import AppBadge from '@/components/AppBadge.vue'
import AppBanner from '@/components/AppBanner.vue'
import AppButton from '@/components/AppButton.vue'
import AppDialog from '@/components/AppDialog.vue'
import AppIcon from '@/components/AppIcon.vue'
import AppMenu from '@/components/AppMenu.vue'
import DateLabel from '@/components/DateLabel.vue'
import EmptyState from '@/components/EmptyState.vue'
import IconButton from '@/components/IconButton.vue'
import RadioGroup from '@/components/RadioGroup.vue'
import SelectField from '@/components/SelectField.vue'
import SidebarItem from '@/components/SidebarItem.vue'
import SkeletonBlock from '@/components/SkeletonBlock.vue'
import StatusChip from '@/components/StatusChip.vue'
import TextField from '@/components/TextField.vue'
import VideoRow from '@/components/VideoRow.vue'

describe('the looks of a button', () => {
  it('R-TH-06: a quiet and a destructive button have looks of their own, from tokens', () => {
    render(AppButton, { props: { variant: 'ghost' }, slots: { default: 'Cancel' } })
    render(AppButton, { props: { variant: 'danger' }, slots: { default: 'Remove channel' } })

    const ghost = screen.getByRole('button', { name: 'Cancel' }).className
    const danger = screen.getByRole('button', { name: 'Remove channel' }).className

    expect(ghost).toContain('text-text-muted')
    expect(ghost).not.toContain('bg-accent')
    expect(danger).toContain('bg-err-bg')
    expect(danger).toContain('text-err-text')
  })

  it('R-UI-11: a busy button says so and cannot be pressed twice', () => {
    render(AppButton, { props: { busy: true }, slots: { default: 'Check now' } })

    const button = screen.getByRole('button', { name: 'Check now' }) as HTMLButtonElement

    expect(button.getAttribute('aria-busy')).toBe('true')
    expect(button.disabled).toBe(true)
  })
})

describe('the icon in three sizes', () => {
  it.each([
    ['sm', 'size-3'],
    ['md', 'size-4'],
    ['lg', 'size-5'],
  ] as const)('R-TH-06: the %s icon takes a step of the spacing scale', (size, className) => {
    const { container } = render(AppIcon, { props: { name: 'clock', size } })

    expect(container.querySelector('svg')?.getAttribute('class')).toContain(className)
  })
})

describe('the icon button', () => {
  it('R-UI-14: has its label as accessible name and as tooltip, and reports a press', async () => {
    const { emitted } = render(IconButton, { props: { icon: 'more', label: 'More actions' } })

    const button = screen.getByRole('button', { name: 'More actions' })
    await fireEvent.click(button)

    expect(button.getAttribute('title')).toBe('More actions')
    expect(button.className).toContain('size-11')
    expect(emitted().press).toHaveLength(1)
  })

  it('R-UI-11: the small one is 36 px, and a busy one cannot be pressed', () => {
    render(IconButton, { props: { icon: 'retry', label: 'Check all', size: 'sm', busy: true } })

    const button = screen.getByRole('button', { name: 'Check all' }) as HTMLButtonElement

    expect(button.className).toContain('size-9')
    expect(button.disabled).toBe(true)
  })
})

describe('the banner that only tells something', () => {
  it('R-FB-04: an info banner waits its turn and has an icon of its own', () => {
    render(AppBanner, { props: { tone: 'info' }, slots: { default: 'Added before' } })

    const banner = screen.getByRole('status')

    expect(banner.className).toContain('bg-ok-bg')
    expect(banner.querySelector('svg')?.getAttribute('data-icon')).toBe('info')
  })
})

describe('the dialog', () => {
  function open() {
    return render(AppDialog, {
      props: { title: 'Remove Sample Channel?', closeLabel: 'Close' },
      slots: {
        default: () => h('input', { 'aria-label': 'Name', 'data-autofocus': '' }),
        actions: () => [h('button', 'Cancel'), h('button', 'Remove channel')],
      },
    })
  }

  it('R-UI-14: is a modal dialog named by its title', () => {
    open()

    const dialog = screen.getByRole('dialog', { name: 'Remove Sample Channel?' })

    expect(dialog.getAttribute('aria-modal')).toBe('true')
    expect(within(dialog).getByRole('heading', { level: 2 }).textContent).toContain('Remove')
  })

  it('R-UI-14: gives the focus to the field that asks for it', async () => {
    open()
    await nextTick()

    expect(document.activeElement).toBe(screen.getByLabelText('Name'))
  })

  it('R-UI-13: Escape, the close button and a click beside it close it', async () => {
    const { emitted, container } = open()

    await fireEvent.keyDown(screen.getByRole('dialog'), { key: 'Escape' })
    await fireEvent.click(screen.getByRole('button', { name: 'Close' }))
    await fireEvent.mouseDown(container.querySelector('[data-dialog-backdrop]') as Element)
    await fireEvent.mouseDown(screen.getByRole('dialog'))

    expect(emitted().close).toHaveLength(3)
  })

  it('R-UI-13: the Tab key stays inside the dialog', async () => {
    open()
    await nextTick()
    const dialog = screen.getByRole('dialog')
    const first = screen.getByRole('button', { name: 'Close' })
    const last = screen.getByRole('button', { name: 'Remove channel' })

    last.focus()
    await fireEvent.keyDown(dialog, { key: 'Tab' })
    const afterForward = document.activeElement
    await fireEvent.keyDown(dialog, { key: 'Tab', shiftKey: true })
    const afterBack = document.activeElement
    screen.getByLabelText('Name').focus()
    await fireEvent.keyDown(dialog, { key: 'Tab' })
    await fireEvent.keyDown(dialog, { key: 'a' })

    expect(afterForward).toBe(first)
    expect(afterBack).toBe(last)
    expect(document.activeElement).toBe(screen.getByLabelText('Name'))
  })

  it('R-UI-14: gives the focus back to where it was when it goes', () => {
    const opener = document.createElement('button')
    document.body.append(opener)
    opener.focus()

    const { unmount } = open()
    unmount()

    expect(document.activeElement).toBe(opener)
    opener.remove()
  })

  it('R-TH-08: drawn in the flow of a page it is no modal and takes no focus', () => {
    const before = document.activeElement
    render(AppDialog, { props: { title: 'A sample', closeLabel: 'Close', inline: true } })

    expect(screen.getByRole('dialog').getAttribute('aria-modal')).toBeNull()
    expect(document.activeElement).toBe(before)
  })
})

describe('the text field', () => {
  it('R-UI-14: has a label, passes on what is typed, and reports Enter', async () => {
    const { emitted } = render(TextField, {
      props: { modelValue: '', label: 'Channel link', placeholder: 'https://', hint: 'A hint' },
    })

    const field = screen.getByLabelText('Channel link') as HTMLInputElement
    await fireEvent.update(field, '@sample')
    await fireEvent.keyDown(field, { key: 'Enter' })

    expect(field.placeholder).toBe('https://')
    expect(emitted()['update:modelValue']).toEqual([['@sample']])
    expect(emitted().enter).toHaveLength(1)
    expect(screen.getByText('A hint').id).toBe(field.getAttribute('aria-describedby'))
  })

  it('R-UI-14: what is wrong is announced and takes the place of the hint', () => {
    render(TextField, {
      props: { modelValue: 'x', label: 'Channel link', hint: 'A hint', error: 'Not a channel' },
    })

    const field = screen.getByLabelText('Channel link')

    expect(screen.getByRole('alert').textContent).toBe('Not a channel')
    expect(screen.queryByText('A hint')).toBeNull()
    expect(field.getAttribute('aria-invalid')).toBe('true')
  })

  it('R-UI-14: a hidden label is still there for screen readers', () => {
    render(TextField, {
      props: { modelValue: '', label: 'Channel link', hideLabel: true, type: 'date' },
    })

    const field = screen.getByLabelText('Channel link') as HTMLInputElement

    expect(screen.getByText('Channel link').className).toContain('sr-only')
    expect(field.type).toBe('date')
    expect(field.getAttribute('aria-describedby')).toBeNull()
  })
})

describe('the select', () => {
  it('R-UI-14: has a label, shows its options and passes on the choice', async () => {
    const { emitted } = render(SelectField, {
      props: {
        modelValue: 'best',
        label: 'Quality',
        hint: 'Applies to new downloads.',
        options: [
          { value: 'best', label: 'Use default' },
          { value: '1080', label: '1080p' },
        ],
      },
    })

    const select = screen.getByLabelText('Quality') as HTMLSelectElement
    await fireEvent.update(select, '1080')

    expect([...select.options].map((option) => option.text)).toEqual(['Use default', '1080p'])
    expect(emitted()['update:modelValue']).toEqual([['1080']])
    expect(screen.getByText('Applies to new downloads.').id).toBe(
      select.getAttribute('aria-describedby'),
    )
  })
})

describe('the radio group', () => {
  const options = [
    { value: 'pick', label: 'Let me pick', hint: 'Nothing downloads.' },
    { value: 'after', label: 'Only after a date' },
  ]

  it('R-UI-14: is a named group of radio buttons, one of them chosen', async () => {
    const { emitted } = render(RadioGroup, {
      props: { modelValue: 'pick', legend: 'What to mirror', options },
    })

    const group = screen.getByRole('group', { name: 'What to mirror' })
    const radios = within(group).getAllByRole('radio') as HTMLInputElement[]
    const chosenBefore = radios.map((radio) => radio.checked)
    await fireEvent.click(screen.getByLabelText('Only after a date'))

    expect(chosenBefore).toEqual([true, false])
    expect(new Set(radios.map((radio) => radio.name)).size).toBe(1)
    expect(screen.getByText('Nothing downloads.')).toBeTruthy()
    expect(emitted()['update:modelValue']).toEqual([['after']])
  })

  it('R-CH-05: what belongs to one option is shown only while that option is chosen', () => {
    const slots = { extra: () => h('input', { 'aria-label': 'Date' }) }
    render(RadioGroup, { props: { modelValue: 'after', legend: 'What', options }, slots })

    expect(screen.getAllByLabelText('Date')).toHaveLength(1)
  })
})

describe('the status chip and the badge', () => {
  it.each([
    ['plain', 'border-line-strong'],
    ['neutral', 'bg-neutral-bg'],
    ['ok', 'bg-ok-bg'],
    ['progress', 'bg-warn-bg'],
    ['failed', 'bg-err-bg'],
  ] as const)('R-FB-02: the %s chip has its own look and its words', (tone, className) => {
    render(StatusChip, { props: { tone, icon: 'check' }, slots: { default: 'A status' } })

    const chip = screen.getByText('A status')

    expect(chip.className).toContain(className)
    expect(chip.querySelector('svg')?.getAttribute('aria-hidden')).toBe('true')
  })

  it('R-FB-02: a chip without an icon is words only', () => {
    render(StatusChip, { slots: { default: 'Not downloaded' } })

    expect(screen.getByText('Not downloaded').querySelector('svg')).toBeNull()
  })

  it('R-CH-34: the badge for new videos is dark text on the "new" colour', () => {
    render(AppBadge, { slots: { default: '3 new' } })
    render(AppBadge, { props: { shape: 'tag' }, slots: { default: 'New' } })

    const pill = screen.getByText('3 new').className
    const tag = screen.getByText('New').className

    expect(pill).toContain('bg-warn')
    expect(pill).toContain('text-on-warn')
    expect(pill).toContain('rounded-full')
    expect(tag).toContain('rounded-xs')
  })
})

describe('the menu', () => {
  const items = [
    { id: 'check', label: 'Check now', icon: 'retry' as const },
    { id: 'youtube', label: 'Open on YouTube', href: 'https://www.youtube.com/channel/UCa' },
    { id: 'remove', label: 'Remove channel', danger: true },
  ]

  function open(at?: { x: number; y: number }) {
    return render(AppMenu, { props: { label: 'Channel actions', items, at } })
  }

  it('R-UI-14: is a named menu whose items are named by their words', async () => {
    open()
    await Promise.resolve()

    const menu = screen.getByRole('menu', { name: 'Channel actions' })

    expect(
      within(menu)
        .getAllByRole('menuitem')
        .map((item) => item.textContent?.trim()),
    ).toEqual(['Check now', 'Open on YouTube', 'Remove channel'])
    expect(screen.getByRole('menuitem', { name: 'Remove channel' }).className).toContain(
      'text-err-text',
    )
  })

  it('R-UI-13: opens with the focus on its first item, and the arrow keys move it', async () => {
    open()
    const menu = screen.getByRole('menu')
    await new Promise((done) => setTimeout(done))
    const names = (): string | undefined => document.activeElement?.textContent?.trim()

    const first = names()
    await fireEvent.keyDown(menu, { key: 'ArrowDown' })
    const second = names()
    await fireEvent.keyDown(menu, { key: 'End' })
    const last = names()
    await fireEvent.keyDown(menu, { key: 'ArrowDown' })
    const wrapped = names()
    await fireEvent.keyDown(menu, { key: 'ArrowUp' })
    const back = names()
    await fireEvent.keyDown(menu, { key: 'Home' })
    await fireEvent.keyDown(menu, { key: 'x' })

    expect([first, second, last, wrapped, back, names()]).toEqual([
      'Check now',
      'Open on YouTube',
      'Remove channel',
      'Check now',
      'Remove channel',
      'Check now',
    ])
  })

  it('R-UI-13: choosing an item tells which one and closes the menu', async () => {
    const { emitted } = open()

    await fireEvent.click(screen.getByRole('menuitem', { name: 'Check now' }))

    expect(emitted().choose).toEqual([['check']])
    expect(emitted().close).toHaveLength(1)
  })

  it('R-CH-30: an item that leaves the app is a link that opens in the browser', async () => {
    const { emitted } = open()

    const link = screen.getByRole('menuitem', { name: 'Open on YouTube' }) as HTMLAnchorElement
    link.addEventListener('click', (event) => event.preventDefault())
    await fireEvent.click(link)

    expect(link.tagName).toBe('A')
    expect(link.target).toBe('_blank')
    expect(link.href).toBe('https://www.youtube.com/channel/UCa')
    expect(emitted().choose).toEqual([['youtube']])
  })

  it('R-UI-13: Escape, Tab and a click elsewhere close it', async () => {
    const { emitted } = open()
    const menu = screen.getByRole('menu')

    await fireEvent.keyDown(menu, { key: 'Escape' })
    await fireEvent.keyDown(menu, { key: 'Tab' })
    await fireEvent.mouseDown(document.body)
    await fireEvent.mouseDown(menu)

    expect(emitted().close).toHaveLength(3)
  })

  it('R-CH-30: opened by a right-click it appears where the pointer is', () => {
    open({ x: 120, y: 80 })

    const menu = screen.getByRole('menu')

    expect(menu.className).toContain('fixed')
    expect(menu.style.left).toBe('120px')
    expect(menu.style.top).toBe('80px')
  })

  it('R-UI-14: gives the focus back when it goes, and stops listening for clicks', async () => {
    const opener = document.createElement('button')
    document.body.append(opener)
    opener.focus()
    const { unmount, emitted } = open()

    unmount()
    await fireEvent.mouseDown(document.body)

    expect(document.activeElement).toBe(opener)
    expect(emitted().close).toBeUndefined()
    opener.remove()
  })
})

describe('the sidebar item', () => {
  const props = {
    title: 'Sample Channel One',
    status: 'Up to date · checked 2 min ago',
    statusIcon: 'check' as const,
  }

  it('R-CH-34: shows the avatar, the name, one status line with an icon, and the new count', () => {
    render(SidebarItem, {
      props: { ...props, avatar: '/api/channels/UCa/avatar', newVideos: '3 new', statusTone: 'ok' },
    })

    const item = screen.getByRole('button', { name: /Sample Channel One/ })
    const status = item.querySelector('[data-status]')

    expect(item.querySelector('img')?.getAttribute('src')).toBe('/api/channels/UCa/avatar')
    expect(status?.textContent).toContain('Up to date · checked 2 min ago')
    expect(status?.querySelector('svg')?.getAttribute('data-icon')).toBe('check')
    expect(status?.className).toContain('text-ok-text')
    expect(within(item).getByText('3 new')).toBeTruthy()
  })

  it('R-CH-34: a channel without new videos and without a picture shows neither', async () => {
    render(SidebarItem, { props: { ...props, avatar: '/missing' } })
    const item = screen.getByRole('button')

    await fireEvent.error(item.querySelector('img') as Element)

    expect(item.querySelector('img')).toBeNull()
    expect(item.querySelector('[data-badge]')).toBeNull()
    expect(item.getAttribute('aria-current')).toBeNull()
  })

  it('R-UI-01: the open channel is marked, a click opens, a right-click asks for the menu', async () => {
    const { emitted } = render(SidebarItem, { props: { ...props, selected: true } })
    const item = screen.getByRole('button')

    await fireEvent.click(item)
    await fireEvent.contextMenu(item, { clientX: 40, clientY: 90 })

    expect(item.getAttribute('aria-current')).toBe('page')
    expect(emitted().open).toHaveLength(1)
    expect(emitted().menu).toEqual([[{ x: 40, y: 90 }]])
  })
})

describe('the date of a video', () => {
  it('R-DT-13: an exact date is plain text without an icon', () => {
    const { container } = render(DateLabel, { props: { text: '11 Nov 2026' } })

    const label = container.querySelector('[data-date="exact"]')

    expect(label?.textContent).toBe('11 Nov 2026')
    expect(container.querySelector('svg')).toBeNull()
  })

  it('R-DT-13: a waiting date is dimmed, has a clock icon and says what it waits for', () => {
    const { container } = render(DateLabel, {
      props: { text: 'around 2005', approximate: true, note: 'Exact date pending' },
    })

    const label = container.querySelector('[data-date="waiting"]')

    expect(label?.textContent).toContain('around 2005')
    expect(label?.getAttribute('title')).toBe('Exact date pending')
    expect(label?.className).toContain('text-text-muted')
    expect(label?.querySelector('svg')?.getAttribute('data-icon')).toBe('clock')
    expect(label?.querySelector('.sr-only')?.textContent).toBe('Exact date pending')
  })

  it('R-DT-04: a video without any date shows its words and nothing made up', () => {
    const { container } = render(DateLabel, { props: { text: 'date pending', approximate: true } })

    expect(container.textContent).toBe('date pending')
    expect(container.querySelector('.sr-only')).toBeNull()
  })
})

describe('the video row', () => {
  it('R-CH-10: shows thumbnail, duration, title, facts and status of one video', () => {
    render(VideoRow, {
      props: {
        title: 'Building a cabin',
        thumbnail: '/api/videos/v1/thumbnail',
        duration: '24:18',
        newTag: 'New',
      },
      slots: { facts: '48K views', status: 'Not downloaded' },
    })

    const row = screen.getByRole('listitem')
    const picture = row.querySelector('img')

    expect(picture?.getAttribute('src')).toBe('/api/videos/v1/thumbnail')
    expect(picture?.getAttribute('loading')).toBe('lazy')
    expect(picture?.getAttribute('alt')).toBe('')
    expect(row.querySelector('[data-duration]')?.textContent?.trim()).toBe('24:18')
    expect(row.querySelector('[data-title]')?.textContent).toBe('Building a cabin')
    expect(row.querySelector('[data-facts]')?.textContent).toBe('48K views')
    expect(within(row).getByText('New').className).toContain('bg-warn')
    expect(row.textContent).toContain('Not downloaded')
  })

  it('R-CH-16: a thumbnail that is not cached leaves the plain block, and nothing is made up', async () => {
    render(VideoRow, { props: { title: 'No picture', thumbnail: '/missing' } })
    const row = screen.getByRole('listitem')

    await fireEvent.error(row.querySelector('img') as Element)

    expect(row.querySelector('img')).toBeNull()
    expect(row.querySelector('[data-duration]')).toBeNull()
    expect(row.querySelector('[data-badge]')).toBeNull()
  })
})

describe('loading and empty', () => {
  it('R-CH-11: a skeleton is a grey block that says nothing to a screen reader', () => {
    const { container } = render(SkeletonBlock)

    const block = container.querySelector('[data-skeleton]')

    expect(block?.getAttribute('aria-hidden')).toBe('true')
    expect(block?.className).toContain('bg-track')
  })

  it('R-UI-14: an empty state has a heading, a sentence and room for a way forward', () => {
    render(EmptyState, {
      props: { title: 'No videos yet', icon: 'video' },
      slots: { default: 'Nothing is listed.', action: () => h('button', 'Check now') },
    })

    expect(screen.getByRole('heading', { level: 2, name: 'No videos yet' })).toBeTruthy()
    expect(screen.getByText('Nothing is listed.')).toBeTruthy()
    expect(screen.getByRole('button', { name: 'Check now' })).toBeTruthy()
  })
})

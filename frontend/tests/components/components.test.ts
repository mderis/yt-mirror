import { fireEvent, render, screen } from '@testing-library/vue'
import { describe, expect, it } from 'vitest'
import { h } from 'vue'

import AppBanner from '@/components/AppBanner.vue'
import AppButton from '@/components/AppButton.vue'
import AppIcon from '@/components/AppIcon.vue'
import { ICON_NAMES } from '@/components/icons'
import ProgressBar from '@/components/ProgressBar.vue'

describe('the button', () => {
  it('R-UI-14: is a real button with its label as its accessible name', async () => {
    const { emitted } = render(AppButton, { slots: { default: 'Mirror' } })

    const button = screen.getByRole('button', { name: 'Mirror' })
    await fireEvent.click(button)

    expect(button.getAttribute('type')).toBe('button')
    expect(emitted().press).toHaveLength(1)
  })

  it('R-UI-14: a disabled button is disabled for the browser and looks it', () => {
    render(AppButton, {
      props: { disabled: true, variant: 'primary' },
      slots: { default: 'Continue' },
    })

    const button = screen.getByRole('button', { name: 'Continue' }) as HTMLButtonElement

    expect(button.disabled).toBe(true)
    expect(button.className).toContain('disabled:opacity-50')
  })

  it('R-TH-06: the two looks differ and use only token classes', () => {
    render(AppButton, { props: { variant: 'primary' }, slots: { default: 'One' } })
    render(AppButton, { slots: { default: 'Two' } })

    const primary = screen.getByRole('button', { name: 'One' }).className
    const secondary = screen.getByRole('button', { name: 'Two' }).className

    expect(primary).toContain('bg-accent')
    expect(primary).toContain('text-on-accent')
    expect(secondary).toContain('border-line-strong')
    expect(secondary).not.toContain('bg-accent')
  })

  it('R-UI-14: an icon in front of the label is hidden from screen readers', () => {
    render(AppButton, { props: { icon: 'retry' }, slots: { default: 'Try again' } })

    const icon = screen.getByRole('button', { name: 'Try again' }).querySelector('svg')

    expect(icon?.getAttribute('aria-hidden')).toBe('true')
    expect(icon?.getAttribute('data-icon')).toBe('retry')
  })
})

describe('the icon', () => {
  it.each(ICON_NAMES)('R-UI-14: the %s icon is drawn with strokes in the text colour', (name) => {
    const { container } = render(AppIcon, { props: { name } })
    const icon = container.querySelector('svg')

    expect(icon?.getAttribute('stroke')).toBe('currentColor')
    expect(icon?.getAttribute('fill')).toBe('none')
    expect(icon?.querySelectorAll('path, circle').length).toBeGreaterThan(0)
  })
})

describe('the progress bar', () => {
  it('R-UI-14: says its progress to screen readers and draws it as a width', () => {
    render(ProgressBar, { props: { value: 0.64, label: 'Progress of ffmpeg' } })

    const bar = screen.getByRole('progressbar', { name: 'Progress of ffmpeg' })

    expect(bar.getAttribute('aria-valuenow')).toBe('64')
    expect(bar.getAttribute('aria-valuemin')).toBe('0')
    expect(bar.getAttribute('aria-valuemax')).toBe('100')
    expect((bar.firstElementChild as HTMLElement).style.width).toBe('64%')
  })

  it.each([
    [-0.5, '0'],
    [0, '0'],
    [0.999, '100'],
    [3, '100'],
  ])('R-UI-11: a value of %s is shown as %s percent', (value, shown) => {
    render(ProgressBar, { props: { value, label: 'Progress' } })

    expect(screen.getByRole('progressbar').getAttribute('aria-valuenow')).toBe(shown)
  })

  it('R-UI-11: unknown progress has no number and a dimmed full bar', () => {
    render(ProgressBar, { props: { value: null, label: 'Progress' } })

    const bar = screen.getByRole('progressbar')

    expect(bar.hasAttribute('aria-valuenow')).toBe(false)
    expect((bar.firstElementChild as HTMLElement).style.width).toBe('100%')
    expect(bar.firstElementChild?.className).toContain('opacity-50')
  })
})

describe('the banner', () => {
  it('R-FB-04: shows its message and the action that fixes the condition', () => {
    render(AppBanner, {
      slots: {
        default: 'ffmpeg is missing.',
        action: () => h('button', { type: 'button' }, 'Install now'),
      },
    })

    const banner = screen.getByRole('status')

    expect(banner.textContent).toContain('ffmpeg is missing.')
    expect(screen.getByRole('button', { name: 'Install now' })).toBeTruthy()
    expect(banner.className).toContain('bg-warn-bg')
    expect(banner.querySelector('svg')?.getAttribute('data-icon')).toBe('warning')
  })

  it('R-FB-04, R-UI-14: a failure is announced at once and looks different', () => {
    render(AppBanner, { props: { tone: 'error' }, slots: { default: 'It failed.' } })

    const banner = screen.getByRole('alert')

    expect(banner.textContent).toContain('It failed.')
    expect(banner.className).toContain('bg-err-bg')
    expect(screen.queryByRole('status')).toBeNull()
  })
})

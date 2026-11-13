/** Initial theme choice, following the OS, and applying switches. */
import { act, render, screen } from '@testing-library/react'
import { beforeEach, describe, expect, it, vi } from 'vitest'

import type { UiSettings } from '../services/uiSettings'
import { withSuppressedRenderErrors } from '../test-support/renderErrors'
import { ThemeProvider, useTheme } from './index'

function settingsOf(overrides: Partial<UiSettings> = {}): UiSettings {
  return { languages: ['en'], default_locale: 'en', default_theme: 'system', ...overrides }
}

/**
 * Replaces `matchMedia` so OS-side switches can be fired.
 * jsdom's implementation does not emit `change`, so verifying the subscription needs a replacement.
 */
function stubMatchMedia(matches: boolean) {
  const listeners = new Set<(event: MediaQueryListEvent) => void>()
  const query = {
    matches,
    addEventListener: (_type: string, handle: (event: MediaQueryListEvent) => void) => {
      listeners.add(handle)
    },
    removeEventListener: (_type: string, handle: (event: MediaQueryListEvent) => void) => {
      listeners.delete(handle)
    },
  }
  vi.stubGlobal(
    'matchMedia',
    vi.fn(() => query),
  )
  return {
    emit(next: boolean) {
      query.matches = next
      for (const handle of listeners) {
        handle({ matches: next } as MediaQueryListEvent)
      }
    },
    listenerCount: () => listeners.size,
  }
}

function Probe() {
  const { theme, resolvedTheme, setTheme } = useTheme()
  return (
    <div>
      <span data-testid="theme">{theme}</span>
      <span data-testid="resolved">{resolvedTheme}</span>
      <button
        onClick={() => {
          setTheme('light')
        }}
      >
        light
      </button>
    </div>
  )
}

function renderWith(settings: UiSettings) {
  return render(
    <ThemeProvider settings={settings}>
      <Probe />
    </ThemeProvider>,
  )
}

describe('ThemeProvider', () => {
  beforeEach(() => {
    localStorage.clear()
    vi.unstubAllGlobals()
    document.documentElement.removeAttribute('data-theme')
  })

  it('gives top priority to the user choice (localStorage)', () => {
    stubMatchMedia(false)
    localStorage.setItem('theme', 'dark')
    renderWith(settingsOf({ default_theme: 'light' }))
    expect(screen.getByTestId('theme').textContent).toBe('dark')
    expect(screen.getByTestId('resolved').textContent).toBe('dark')
  })

  it('uses the server default when nothing is chosen', () => {
    stubMatchMedia(false)
    renderWith(settingsOf({ default_theme: 'light' }))
    expect(screen.getByTestId('theme').textContent).toBe('light')
  })

  it('falls back to light when the default is invalid (even if the OS is dark)', () => {
    stubMatchMedia(true)
    renderWith(settingsOf({ default_theme: 'solarized' }))
    expect(screen.getByTestId('theme').textContent).toBe('light')
    expect(screen.getByTestId('resolved').textContent).toBe('light')
  })

  it('resolves to the OS color scheme for system', () => {
    stubMatchMedia(true)
    renderWith(settingsOf({ default_theme: 'system' }))
    expect(screen.getByTestId('resolved').textContent).toBe('dark')
  })

  it('follows OS-side switches while on system', () => {
    const media = stubMatchMedia(false)
    renderWith(settingsOf({ default_theme: 'system' }))
    expect(screen.getByTestId('resolved').textContent).toBe('light')

    act(() => {
      media.emit(true)
    })
    expect(screen.getByTestId('resolved').textContent).toBe('dark')
  })

  it('an explicitly chosen theme is unaffected by OS changes', () => {
    const media = stubMatchMedia(false)
    localStorage.setItem('theme', 'light')
    renderWith(settingsOf())

    act(() => {
      media.emit(true)
    })
    expect(screen.getByTestId('resolved').textContent).toBe('light')
  })

  it('applies the resolved value to <html data-theme> and colorScheme', () => {
    stubMatchMedia(true)
    renderWith(settingsOf({ default_theme: 'system' }))
    expect(document.documentElement.dataset.theme).toBe('dark')
    expect(document.documentElement.style.colorScheme).toBe('dark')
  })

  it('saves the choice to localStorage', () => {
    stubMatchMedia(false)
    renderWith(settingsOf({ default_theme: 'dark' }))

    act(() => {
      screen.getByRole('button', { name: 'light' }).click()
    })
    expect(localStorage.getItem('theme')).toBe('light')
    expect(screen.getByTestId('resolved').textContent).toBe('light')
  })

  it('unsubscribes from the OS on unmount', () => {
    const media = stubMatchMedia(false)
    const { unmount } = renderWith(settingsOf())
    expect(media.listenerCount()).toBe(1)

    unmount()
    expect(media.listenerCount()).toBe(0)
  })
})

describe('useTheme', () => {
  it('throws when used outside the Provider', () => {
    stubMatchMedia(false)
    try {
      withSuppressedRenderErrors(() => {
        expect(() => render(<Probe />)).toThrow(/ThemeProvider/)
      })
    } finally {
      vi.unstubAllGlobals()
    }
  })
})

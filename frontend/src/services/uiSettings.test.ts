/** Fetching initial UI settings (including the fallback when the server is unreachable). */
import { afterEach, describe, expect, it, vi } from 'vitest'

import { FALLBACK_UI_SETTINGS, loadUiSettings } from './uiSettings'

function stubFetch(impl: () => Promise<unknown>) {
  vi.stubGlobal('fetch', vi.fn(impl))
}

describe('loadUiSettings', () => {
  afterEach(() => {
    vi.unstubAllGlobals()
  })

  it('uses the server response as is', async () => {
    const payload = { languages: ['ja'], default_locale: 'ja', default_theme: 'dark' }
    stubFetch(() =>
      Promise.resolve({
        ok: true,
        json: () => Promise.resolve(payload),
      }),
    )

    await expect(loadUiSettings()).resolves.toEqual(payload)
  })

  it('falls back to defaults on an error response', async () => {
    stubFetch(() => Promise.resolve({ ok: false, json: () => Promise.resolve({}) }))

    await expect(loadUiSettings()).resolves.toEqual(FALLBACK_UI_SETTINGS)
  })

  it('renders with defaults even if the request itself fails', async () => {
    stubFetch(() => Promise.reject(new Error('offline')))

    await expect(loadUiSettings()).resolves.toEqual(FALLBACK_UI_SETTINGS)
  })
})

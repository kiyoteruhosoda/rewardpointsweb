/**
 * Initial screen settings (language and theme).
 *
 * Receives the defaults chosen by the operator in the admin console from the server and uses them
 * as initial values while the user has not chosen anything. They are needed before login too,
 * so they are fetched once before authentication (`main.tsx`).
 */

export interface UiSettings {
  languages: string[]
  default_locale: string
  default_theme: string
}

/** Fallback so the screen still renders when the server is unreachable. */
export const FALLBACK_UI_SETTINGS: UiSettings = {
  languages: ['en', 'ja'],
  default_locale: 'en',
  default_theme: 'light',
}

export async function loadUiSettings(): Promise<UiSettings> {
  try {
    const response = await fetch('/api/ui/settings')
    if (!response.ok) return FALLBACK_UI_SETTINGS
    return (await response.json()) as UiSettings
  } catch {
    return FALLBACK_UI_SETTINGS
  }
}

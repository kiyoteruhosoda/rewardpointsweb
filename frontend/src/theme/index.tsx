/**
 * Theme switching (light / dark / follow OS).
 *
 * The chosen theme goes on `<html data-theme>`, and colors are resolved by CSS variables
 * in index.css. The JavaScript side only decides which color scheme to use and holds no colors itself.
 *
 * Priority is "user choice (localStorage) > server default (DEFAULT_THEME)".
 * Choosing `system` follows the OS setting and reacts immediately to OS-side changes.
 * When neither decides, use light (matching the server default).
 */
import {
  createContext,
  useCallback,
  useContext,
  useEffect,
  useMemo,
  useState,
  type ReactNode,
} from 'react'

import type { UiSettings } from '../services/uiSettings'

export type ThemePreference = 'system' | 'light' | 'dark'
/** The color scheme actually applied (`system` resolved). */
export type ResolvedTheme = 'light' | 'dark'

export const THEME_PREFERENCES: ThemePreference[] = ['system', 'light', 'dark']

const STORAGE_KEY = 'theme'
const DARK_QUERY = '(prefers-color-scheme: dark)'
/** Color scheme when nothing decides. Same default as the server's DEFAULT_THEME. */
const FALLBACK_PREFERENCE: ThemePreference = 'light'

interface ThemeValue {
  theme: ThemePreference
  resolvedTheme: ResolvedTheme
  setTheme: (theme: ThemePreference) => void
}

const ThemeContext = createContext<ThemeValue | null>(null)

function isThemePreference(value: unknown): value is ThemePreference {
  return value === 'system' || value === 'light' || value === 'dark'
}

function initialTheme(settings: UiSettings): ThemePreference {
  const stored = localStorage.getItem(STORAGE_KEY)
  if (isThemePreference(stored)) return stored
  return isThemePreference(settings.default_theme) ? settings.default_theme : FALLBACK_PREFERENCE
}

function prefersDark(): boolean {
  return window.matchMedia(DARK_QUERY).matches
}

export function ThemeProvider({
  settings,
  children,
}: {
  settings: UiSettings
  children: ReactNode
}) {
  const [theme, setThemeState] = useState<ThemePreference>(() => initialTheme(settings))
  const [systemTheme, setSystemTheme] = useState<ResolvedTheme>(() =>
    prefersDark() ? 'dark' : 'light',
  )

  // Follow OS-side changes (keep subscribing even when something other than `system` is chosen,
  // so no stale value remains after switching back to `system`).
  useEffect(() => {
    const query = window.matchMedia(DARK_QUERY)
    const handle = (event: MediaQueryListEvent) => {
      setSystemTheme(event.matches ? 'dark' : 'light')
    }
    query.addEventListener('change', handle)
    return () => {
      query.removeEventListener('change', handle)
    }
  }, [])

  const resolvedTheme: ResolvedTheme = theme === 'system' ? systemTheme : theme

  useEffect(() => {
    document.documentElement.dataset.theme = resolvedTheme
    // Make browser-default UI such as form controls match the color scheme too
    document.documentElement.style.colorScheme = resolvedTheme
  }, [resolvedTheme])

  const setTheme = useCallback((next: ThemePreference) => {
    localStorage.setItem(STORAGE_KEY, next)
    setThemeState(next)
  }, [])

  const value = useMemo(
    () => ({ theme, resolvedTheme, setTheme }),
    [theme, resolvedTheme, setTheme],
  )
  return <ThemeContext.Provider value={value}>{children}</ThemeContext.Provider>
}

export function useTheme(): ThemeValue {
  const value = useContext(ThemeContext)
  if (!value) throw new Error('useTheme must be used within ThemeProvider')
  return value
}

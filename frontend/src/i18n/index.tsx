/**
 * Lightweight i18n (per-language JSON dictionaries).
 *
 * Define new messages with English keys in en.json and add the Japanese translation to ja.json by hand
 * (see the i18n section in CLAUDE.md).
 *
 * Selection priority is "user choice (localStorage) > browser language >
 * server default (DEFAULT_LOCALE)". The selectable languages can be narrowed by
 * LANGUAGES in the admin screen.
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
import en from './en.json'
import ja from './ja.json'

export type Locale = 'en' | 'ja'

const DICTIONARIES: Record<Locale, Record<string, string>> = { en, ja }
const STORAGE_KEY = 'locale'
/** The language always available when nothing can be chosen (en.json is the translation baseline). */
const FALLBACK_LOCALE: Locale = 'en'

export const LOCALE_LABELS: Record<Locale, string> = {
  en: 'English',
  ja: '日本語',
}

/** Values substituted into `{name}`-style placeholders. */
export type TranslationParams = Record<string, string | number>

interface I18nValue {
  locale: Locale
  /** Selectable languages (narrowed by LANGUAGES in the admin screen). */
  locales: Locale[]
  setLocale: (locale: Locale) => void
  t: (key: string, params?: TranslationParams) => string
}

const I18nContext = createContext<I18nValue | null>(null)

function isLocale(value: unknown): value is Locale {
  return value === 'en' || value === 'ja'
}

function availableLocales(settings: UiSettings): Locale[] {
  const configured = settings.languages.filter(isLocale)
  return configured.length > 0 ? configured : [FALLBACK_LOCALE]
}

function initialLocale(locales: Locale[], settings: UiSettings): Locale {
  const stored = localStorage.getItem(STORAGE_KEY)
  if (isLocale(stored) && locales.includes(stored)) return stored

  const fromBrowser = navigator.language.split('-')[0]
  if (isLocale(fromBrowser) && locales.includes(fromBrowser)) return fromBrowser

  const fromServer = settings.default_locale
  if (isLocale(fromServer) && locales.includes(fromServer)) return fromServer
  return locales[0] ?? FALLBACK_LOCALE
}

/**
 * Replaces keys missing from the dictionary.
 *
 * Passing a code from the server straight to `t()` shows the key string (`error.xxx`) on screen
 * when the code is unknown. Fold it here before rendering.
 */
export function knownMessageKey(key: string, fallback: string): string {
  return key in DICTIONARIES[FALLBACK_LOCALE] ? key : fallback
}

function interpolate(template: string, params?: TranslationParams): string {
  if (!params) return template
  return template.replace(/\{(\w+)\}/g, (match, name: string) =>
    name in params ? String(params[name]) : match,
  )
}

export function I18nProvider({
  settings,
  children,
}: {
  settings: UiSettings
  children: ReactNode
}) {
  const locales = useMemo(() => availableLocales(settings), [settings])
  const [locale, setLocaleState] = useState<Locale>(() => initialLocale(locales, settings))

  // Match <html lang> so screen readers and browser translation work correctly.
  useEffect(() => {
    document.documentElement.lang = locale
  }, [locale])

  const setLocale = useCallback((next: Locale) => {
    localStorage.setItem(STORAGE_KEY, next)
    setLocaleState(next)
  }, [])

  const t = useCallback(
    (key: string, params?: TranslationParams) =>
      interpolate(DICTIONARIES[locale][key] ?? DICTIONARIES.en[key] ?? key, params),
    [locale],
  )

  const value = useMemo(() => ({ locale, locales, setLocale, t }), [locale, locales, setLocale, t])
  return <I18nContext.Provider value={value}>{children}</I18nContext.Provider>
}

export function useI18n(): I18nValue {
  const value = useContext(I18nContext)
  if (!value) throw new Error('useI18n must be used within I18nProvider')
  return value
}

/**
 * Keeps drafts in the tab (sessionStorage) (ADR-0058).
 *
 * When an SSO login cannot continue, the app moves to the login screen, does a full-page round trip with the IdP,
 * then returns to the original screen. React state is lost on the round trip, so **copy the draft here on every edit.**
 * Reading it back with the same key on return also reopens the input dialog that was open.
 *
 * - Cleared when the value becomes `null` (saved or closed)
 * - Everything is cleared on sign-out ({@link clearSessionDrafts}; another person may use the same tab)
 * - In browsers where it cannot be read or written, behaves as plain state only
 */
import { useCallback, useState } from 'react'

const PREFIX = 'draft:'

function read<T>(key: string, initial: T | null): T | null {
  try {
    const raw = window.sessionStorage.getItem(PREFIX + key)
    return raw === null ? initial : (JSON.parse(raw) as T)
  } catch {
    return initial
  }
}

function write(key: string, value: unknown): void {
  try {
    if (value === null) window.sessionStorage.removeItem(PREFIX + key)
    else window.sessionStorage.setItem(PREFIX + key, JSON.stringify(value))
  } catch {
    // Even if it cannot be kept, the draft is still on screen
  }
}

export function useSessionDraft<T>(key: string, initial: T | null = null) {
  const [value, setValue] = useState<T | null>(() => read<T>(key, initial))
  const update = useCallback(
    (next: T | null | ((current: T | null) => T | null)) => {
      setValue((current) => {
        const resolved =
          typeof next === 'function' ? (next as (current: T | null) => T | null)(current) : next
        write(key, resolved)
        return resolved
      })
    },
    [key],
  )
  return [value, update] as const
}

/**
 * Draft for a single input field (a version of {@link useSessionDraft} that is never empty).
 *
 * Input dialogs in this app hold state per field, so use this per field. `initial` when unreadable.
 * ⚠ **Do not use for passwords** (they stay in sessionStorage in plain text).
 */
export function useSessionValue<T>(key: string, initial: T) {
  const [value, setValue] = useSessionDraft<T>(key)
  const update = useCallback(
    (next: T | ((current: T) => T)) => {
      setValue((current) => {
        const base = current ?? initial
        return typeof next === 'function' ? (next as (current: T) => T)(base) : next
      })
    },
    // `initial` is the empty value ('' or []). Recreating it on every render gives the same result, so it is not a dependency
    // eslint-disable-next-line react-hooks/exhaustive-deps
    [setValue],
  )
  return [value ?? initial, update] as const
}

/** Clears all drafts (on sign-out). */
export function clearSessionDrafts(): void {
  try {
    for (const key of Object.keys(window.sessionStorage)) {
      if (key.startsWith(PREFIX)) window.sessionStorage.removeItem(key)
    }
  } catch {
    // Even if it cannot be cleared, the next save overwrites it
  }
}

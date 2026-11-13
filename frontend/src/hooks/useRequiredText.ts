/**
 * Feeds whitespace-only input into the browser's required check as "empty".
 *
 * `required` passes as soon as there is one character, so a whitespace-only reason slips through.
 * Rejecting it later with `trim()` ends the operation with nothing shown on screen (pressing
 * does nothing). Move the check into the input itself and let the browser show its required error.
 *
 * The message is passed with `setCustomValidity()`. The browser's default empty-field message is
 * in the viewer's browser language, which may not match the language chosen in the app.
 */
import { useEffect, useRef } from 'react'

export function useRequiredText(value: string, message: string) {
  const ref = useRef<HTMLInputElement>(null)

  useEffect(() => {
    ref.current?.setCustomValidity(value.trim() === '' ? message : '')
  }, [value, message])

  return ref
}

/**
 * Noise suppression for tests that assert "rendering throws".
 *
 * When React rethrows an exception during rendering, it also sends it to ``console.error`` and
 * window's ``error`` event. jsdom prints the latter straight to stderr, so even
 * tests that pass as expected leave output that looks like a failure. Silence only
 * the expected exceptions.
 */
import { vi } from 'vitest'

/** Suppresses secondary reports of render exceptions only while *act* runs. */
export function withSuppressedRenderErrors<T>(act: () => T): T {
  const silenced = vi.spyOn(console, 'error').mockImplementation(() => undefined)
  const swallow = (event: Event) => {
    event.preventDefault()
  }
  window.addEventListener('error', swallow)
  try {
    return act()
  } finally {
    window.removeEventListener('error', swallow)
    silenced.mockRestore()
  }
}

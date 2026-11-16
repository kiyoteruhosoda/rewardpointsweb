/**
 * Timing of the gacha show (task #1045): about ten seconds from the press to the prize.
 *
 * The handle turns for TURN_MS however fast the server answers, then the result opens and the
 * capsule drops, wobbles and pops open (CSS, about 3.5 s). People who ask for reduced motion
 * get the prize straight away.
 */

/** How long the handle turns before the capsule comes out. */
export const TURN_MS = 6500

export function prefersReducedMotion(): boolean {
  try {
    return window.matchMedia('(prefers-reduced-motion: reduce)').matches
  } catch {
    return false
  }
}

/** Milliseconds still to wait after *startedAt* (both from `Date.now()`). */
export function turnDelay(startedAt: number, now: number, reduced: boolean): number {
  return reduced ? 0 : Math.max(0, TURN_MS - (now - startedAt))
}

/** Resolves once the handle has turned long enough since *startedAt*. */
export function waitForTurn(startedAt: number): Promise<void> {
  const delay = turnDelay(startedAt, Date.now(), prefersReducedMotion())
  return delay === 0
    ? Promise.resolve()
    : new Promise((resolve) => {
        window.setTimeout(resolve, delay)
      })
}

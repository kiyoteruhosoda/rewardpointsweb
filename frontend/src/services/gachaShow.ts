/**
 * Timing of the gacha show (task #1048): about five seconds from the press to the prize.
 *
 * The handle turns for TURN_MS however fast the server answers, a capsule of the prize's colour
 * pops out of the chute (DISPENSE_MS), then the result opens and the capsule pops open (CSS,
 * about 1.5 s). People who ask for reduced motion get the prize straight away.
 */

/** How long the handle turns before the capsule comes out. */
export const TURN_MS = 2500

/** How long the capsule takes to come out of the chute and bounce. */
export const DISPENSE_MS = 1000

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

/** Resolves once the capsule has come out of the chute. */
export function waitForDispense(): Promise<void> {
  return prefersReducedMotion()
    ? Promise.resolve()
    : new Promise((resolve) => {
        window.setTimeout(resolve, DISPENSE_MS)
      })
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

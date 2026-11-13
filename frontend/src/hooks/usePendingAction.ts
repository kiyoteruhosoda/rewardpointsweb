/**
 * Holds the span from press to completion as "in progress" (ADR-0023).
 *
 * Adding a `busy` useState to each screen makes the screens that forgot it look unresponsive.
 * The in-progress flag goes to `ActionButton`'s `pending`, and double submission is also prevented here
 * (calls made while in progress are ignored).
 *
 * The returned `run` returns `void`, so it can be passed straight to `onSubmit` / `onClick`
 * (without tripping `no-misused-promises`).
 *
 * Errors are not swallowed (handle them in the passed function). This only tracks whether it is in progress,
 * and always clears it even on failure.
 */
import { useEffect, useRef, useState } from 'react'

export function usePendingAction<A extends unknown[]>(
  action: (...args: A) => Promise<void>,
): [run: (...args: A) => void, pending: boolean] {
  const [pending, setPending] = useState(false)
  // Track in-progress in a ref as well as state. State updates are not reflected until
  // the next render, too late to judge a quick second press.
  const running = useRef(false)
  const mounted = useRef(true)

  useEffect(() => {
    mounted.current = true
    return () => {
      mounted.current = false
    }
  }, [])

  const run = (...args: A) => {
    if (running.current) return
    running.current = true
    setPending(true)
    void action(...args).finally(() => {
      running.current = false
      // Don't update after succeeding and moving to another screen (this component is gone).
      if (mounted.current) setPending(false)
    })
  }

  return [run, pending]
}

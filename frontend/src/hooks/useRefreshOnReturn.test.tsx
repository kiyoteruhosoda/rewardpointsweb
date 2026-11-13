/** Reloading when the user comes back: the triggers, and the cases where it must not fire. */
import { fireEvent, render } from '@testing-library/react'
import { afterEach, describe, expect, it, vi } from 'vitest'

import { useRefreshOnReturn } from './useRefreshOnReturn'

/** A host that only runs the hook (renders nothing). */
function Probe({ refresh }: { refresh: () => Promise<void> }) {
  useRefreshOnReturn(refresh)
  return null
}

function setVisibility(state: DocumentVisibilityState): void {
  Object.defineProperty(document, 'visibilityState', { configurable: true, value: state })
}

afterEach(() => {
  setVisibility('visible')
})

describe('useRefreshOnReturn', () => {
  it('reloads when brought back to the foreground', () => {
    const refresh = vi.fn<() => Promise<void>>().mockResolvedValue()
    render(<Probe refresh={refresh} />)

    fireEvent(document, new Event('visibilitychange'))

    expect(refresh).toHaveBeenCalledTimes(1)
  })

  it('does not reload when sent to the background (no traffic for an unseen screen)', () => {
    const refresh = vi.fn<() => Promise<void>>().mockResolvedValue()
    render(<Probe refresh={refresh} />)

    setVisibility('hidden')
    fireEvent(document, new Event('visibilitychange'))

    expect(refresh).not.toHaveBeenCalled()
  })

  it('reloads when the connection comes back (what was shown offline was the cache)', () => {
    const refresh = vi.fn<() => Promise<void>>().mockResolvedValue()
    render(<Probe refresh={refresh} />)

    fireEvent(window, new Event('online'))

    expect(refresh).toHaveBeenCalledTimes(1)
  })

  it('does not reload after leaving the screen', () => {
    const refresh = vi.fn<() => Promise<void>>().mockResolvedValue()
    const { unmount } = render(<Probe refresh={refresh} />)

    unmount()
    fireEvent(document, new Event('visibilitychange'))

    expect(refresh).not.toHaveBeenCalled()
  })
})

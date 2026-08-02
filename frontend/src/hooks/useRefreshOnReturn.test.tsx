/** 手元に戻ってきたときの読み直し: きっかけと、鳴らせてはいけない場面。 */
import { fireEvent, render } from '@testing-library/react'
import { afterEach, describe, expect, it, vi } from 'vitest'

import { useRefreshOnReturn } from './useRefreshOnReturn'

/** フックだけを動かすための入れ物（画面は出さない）。 */
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
  it('前面に戻ってきたら読み直す', () => {
    const refresh = vi.fn<() => Promise<void>>().mockResolvedValue()
    render(<Probe refresh={refresh} />)

    fireEvent(document, new Event('visibilitychange'))

    expect(refresh).toHaveBeenCalledTimes(1)
  })

  it('裏に回ったときは読み直さない（見ていない画面のために通信しない）', () => {
    const refresh = vi.fn<() => Promise<void>>().mockResolvedValue()
    render(<Probe refresh={refresh} />)

    setVisibility('hidden')
    fireEvent(document, new Event('visibilitychange'))

    expect(refresh).not.toHaveBeenCalled()
  })

  it('回線が戻ったら読み直す（オフラインで出していたのはキャッシュ）', () => {
    const refresh = vi.fn<() => Promise<void>>().mockResolvedValue()
    render(<Probe refresh={refresh} />)

    fireEvent(window, new Event('online'))

    expect(refresh).toHaveBeenCalledTimes(1)
  })

  it('画面を離れたら読み直さない', () => {
    const refresh = vi.fn<() => Promise<void>>().mockResolvedValue()
    const { unmount } = render(<Probe refresh={refresh} />)

    unmount()
    fireEvent(document, new Event('visibilitychange'))

    expect(refresh).not.toHaveBeenCalled()
  })
})
